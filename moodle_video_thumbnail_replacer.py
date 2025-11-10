#!/usr/bin/env python3
"""
Moodle Quiz Video Link to Thumbnail Replacer

This script automates the process of replacing video links in Moodle quiz
description questions with clickable thumbnails.

Usage:
    python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password>
"""

import argparse
import base64
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError


def login_to_moodle(page: Page, username: str, password: str):
    """Login to Moodle using provided credentials."""
    print("Logging in to Moodle...")
    
    # Check if we're already on the login page or need to navigate to it
    if '/login/index.php' not in page.url:
        # Try to click login link if we're not on the login page
        try:
            page.click('a:has-text("Log in")', timeout=3000)
            page.wait_for_load_state('networkidle')
        except PlaywrightTimeoutError:
            # Might already be redirected or login not needed
            print("  No login link found, assuming already on login page or logged in")
    
    # Wait for login form
    try:
        page.wait_for_selector('input[name="username"]', timeout=5000)
    except PlaywrightTimeoutError:
        print("  Login form not found - might already be logged in")
        return
    
    # Fill in credentials
    print("  Filling in credentials...")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    
    # Submit the form
    print("  Submitting login form...")
    page.click('button[type="submit"], input[type="submit"]')
    
    # Wait for login to complete
    page.wait_for_load_state('networkidle')
    time.sleep(1)
    print("Successfully logged in!")


def click_questions_link(page: Page):
    """Click the Questions link to see all quiz questions."""
    print("Navigating to Questions view...")
    
    # Look for "Questions" link - be specific to avoid clicking wrong links
    try:
        # First try: link with "Questions" text and href containing "mod/quiz/edit.php"
        page.click('a[href*="/mod/quiz/edit.php"]:has-text("Questions")', timeout=5000)
    except PlaywrightTimeoutError:
        try:
            # Second try: any link with exact text "Questions"
            questions_links = page.locator('a:has-text("Questions")').all()
            for link in questions_links:
                href = link.get_attribute('href')
                if href and '/mod/quiz/edit.php' in href:
                    link.click()
                    break
        except:
            # Last resort: just click first Questions link
            page.click('a:has-text("Questions")')
    
    page.wait_for_load_state('networkidle')
    print("Questions page loaded")


def get_description_questions(page: Page) -> list:
    """Get all description type questions from the quiz."""
    print("Finding description questions...")
    
    # Find all li elements with class qtype_description
    questions = page.locator('li.qtype_description').all()
    print(f"Found {len(questions)} description question(s)")
    
    return questions


def extract_edit_link(question_element) -> str:
    """Extract the edit link from a question element."""
    # Find the edit link within the question
    edit_link = question_element.locator('a[title*="Edit question"]').get_attribute('href')
    return edit_link


def find_video_links_in_editor(page: Page) -> list:
    """Find all video links in the TinyMCE editor."""
    print("  Finding video links in question content...")
    
    # Wait for TinyMCE editor to load
    page.wait_for_selector('.tox-tinymce', timeout=10000)
    
    # Get the editor iframe
    editor_frame = page.frame_locator('iframe[id^="id_questiontext_"]')
    
    # Find all links that match the pattern
    links = editor_frame.locator('a[href*="/mod/url/view.php"]').all()

    # Use a set to deduplicate URLs (after inserting thumbnails, same URL appears multiple times)
    video_urls_set = set()
    for link in links:
        href = link.get_attribute('href')
        if href:
            video_urls_set.add(href)

    video_urls = list(video_urls_set)
    print(f"  Found {len(video_urls)} unique video link(s)")
    return video_urls


def download_video_thumbnail(page: Page, video_url: str, temp_dir: Path, debug: bool = False, ms_name: str = None, ms_password: str = None, first_video: bool = False) -> Path:
    """
    Navigate to the video URL, extract thumbnail, and save it.
    Returns the path to the saved thumbnail.
    """
    print(f"  Processing video: {video_url}")
    
    # Open video URL in new tab
    context = page.context
    video_page = context.new_page()
    
    try:
        video_page.goto(video_url, wait_until='networkidle', timeout=30000)
        
        # Wait for the page to load and redirect to SharePoint
        time.sleep(2)
        
        # Handle Microsoft authentication if this is the first video
        if first_video and ms_name and ms_password:
            print("  Handling Microsoft authentication...")
            
            # Check if we're on Microsoft login page
            if 'login.microsoftonline.com' in video_page.url or 'login.windows.net' in video_page.url:
                try:
                    # Wait for and fill in name/email field
                    print("  Filling in name/email...")
                    name_input = video_page.locator('input[type="email"], input[name="loginfmt"]')
                    if name_input.count() > 0:
                        name_input.fill(ms_name)
                        video_page.click('input[type="submit"], button[type="submit"]')
                        time.sleep(2)
                    
                    # Fill in password
                    print("  Filling in password...")
                    password_input = video_page.locator('input[type="password"], input[name="passwd"]')
                    if password_input.count() > 0:
                        password_input.fill(ms_password)
                        video_page.click('input[type="submit"], button[type="submit"]')
                        time.sleep(2)
                    
                    # Handle MFA - wait for user to approve
                    print("\n" + "="*60)
                    print("  MFA REQUIRED: Please approve the sign-in on your device")
                    print("  Waiting for MFA approval and 'Stay signed in?' prompt...")
                    print("="*60)

                    # Handle "Stay signed in?" prompt
                    # Wait up to 60 seconds for the page to appear (don't just sleep)
                    try:
                        # Wait for the "Stay signed in?" page to appear with the title text
                        video_page.wait_for_selector('text=Stay signed in?', timeout=60000)
                        print("  'Stay signed in?' prompt appeared")
                        time.sleep(1)

                        # The Yes button has id="idSIButton9" on the Stay signed in page
                        yes_button = video_page.locator('#idSIButton9[value="Yes"]')
                        if yes_button.count() > 0 and yes_button.is_visible():
                            print("  Found 'Yes' button, clicking to stay signed in...")
                            yes_button.click()
                            time.sleep(2)
                        else:
                            # Fallback to other selectors
                            yes_selectors = [
                                'input[type="submit"][value="Yes"]',
                                'button:has-text("Yes")',
                                'input[value="Yes"]'
                            ]

                            for selector in yes_selectors:
                                yes_btn = video_page.locator(selector)
                                if yes_btn.count() > 0 and yes_btn.is_visible():
                                    print(f"  Found 'Yes' button with selector: {selector}")
                                    yes_btn.first.click()
                                    time.sleep(2)
                                    break

                    except Exception as e:
                        print(f"  No 'Stay signed in' prompt appeared within 60 seconds (this is OK): {e}")

                    # Wait for redirect to SharePoint
                    video_page.wait_for_load_state('networkidle', timeout=15000)
                    print("  Microsoft authentication completed!")
                    
                except Exception as e:
                    print(f"  Warning during Microsoft authentication: {e}")
                    print("  Attempting to continue...")
        
        # Check if this is actually a video link (must contain 'stream.aspx')
        current_url = video_page.url
        if 'stream.aspx' not in current_url:
            print(f"  Skipping - not a video link (URL: {current_url})")
            raise Exception(f"Not a video link - URL does not contain 'stream.aspx': {current_url}")

        print("  Confirmed video link (stream.aspx found)")

        # Wait for video player to load
        time.sleep(3)
        
        if debug:
            print("\n" + "="*60)
            print("DEBUG MODE: Paused on video page")
            print("Current URL:", video_page.url)
            print("Please manually:")
            print("  1. Click 'Video settings' if needed")
            print("  2. Click 'Thumbnail' to display it")
            print("  3. Press Enter here to continue...")
            print("="*60)
            input()
        
        # Check if Video settings panel is visible
        print("  Opening Video settings panel...")
        try:
            # Try to click "Video settings" button if it exists
            # Look for the button by aria-label
            video_settings_button = video_page.locator('button[aria-label="Video settings"]')
            if video_settings_button.count() > 0:
                print("  Found Video settings button, clicking...")
                video_settings_button.click()
                time.sleep(2)
            else:
                print("  Video settings button not found, may already be open")
        except Exception as e:
            print(f"  Could not click Video settings: {e}")
            print("  Panel might already be open or have different structure")
        
        # Click the Thumbnail option
        print("  Clicking Thumbnail option...")
        thumbnail_clicked = False
        
        # Look for the thumbnail button by aria-label
        thumbnail_button = video_page.locator('button[aria-label="Thumbnail"]')
        if thumbnail_button.count() > 0:
            print("  Found Thumbnail button by aria-label...")
            thumbnail_button.first.click()
            time.sleep(2)
            thumbnail_clicked = True

        
        if not thumbnail_clicked:
            raise Exception("Could not click Thumbnail option")
        
        # Wait for thumbnail image to appear
        print("  Waiting for thumbnail to load...")
        time.sleep(3)
        
        # The thumbnail is displayed in the main page within #CollapsibleCustomOptions
        # Look for: <img src="blob:https://ucliveac.sharepoint.com/..." class="ms-Image-image ...">
        thumbnail_img = None

        # First, try looking in the main page within CollapsibleCustomOptions
        print("  Looking for thumbnail in CollapsibleCustomOptions...")
        try:
            # Get the first blob image - it's the thumbnail
            blob_img = video_page.locator('#CollapsibleCustomOptions img[src^="blob:"]').first
            if blob_img.count() > 0:
                blob_url = blob_img.get_attribute('src')
                print(f"  Found blob thumbnail: {blob_url[:60] if blob_url else 'N/A'}...")

                # Download the blob data at full resolution using JavaScript
                # This fetches the actual image file at its intrinsic size
                timestamp = int(time.time() * 1000)
                thumbnail_path = temp_dir / f"thumbnail_{timestamp}.png"

                print("  Fetching blob data at full resolution...")
                image_data = video_page.evaluate('''async (blobUrl) => {
                    const response = await fetch(blobUrl);
                    const blob = await response.blob();
                    return new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.readAsDataURL(blob);
                    });
                }''', blob_url)

                # Decode base64 and save to file
                with open(thumbnail_path, 'wb') as f:
                    f.write(base64.b64decode(image_data))

                print(f"  Saved full-resolution thumbnail to {thumbnail_path}")
                return thumbnail_path

        except Exception as e:
            print(f"  Error downloading blob thumbnail: {e}")

        # If not found in CollapsibleCustomOptions, try main page as fallback
        if not thumbnail_img:
            print("  Thumbnail not found in CollapsibleCustomOptions, checking main page...")
            try:
                # Try different selectors for the thumbnail on main page
                selectors = [
                    'img[src*="thumbnail"]',
                    'img[alt*="Thumbnail"]',
                    'img.ms-Image',
                    'img[role="presentation"]'
                ]
                
                for selector in selectors:
                    imgs = video_page.locator(selector).all()
                    if len(imgs) > 0:
                        # Get the largest image (likely the thumbnail)
                        for img in imgs:
                            src = img.get_attribute('src')
                            if src and ('thumbnail' in src.lower() or 'poster' in src.lower()):
                                box = img.bounding_box()
                                if box and box['width'] > 100 and box['height'] > 100:
                                    thumbnail_img = img
                                    break
                        if thumbnail_img:
                            break
            except Exception as e:
                print(f"  Error finding thumbnail on main page: {e}")
            
            # If we still don't have it, just take the first sizable image
            if not thumbnail_img:
                try:
                    all_imgs = video_page.locator('img').all()
                    for img in all_imgs:
                        box = img.bounding_box()
                        if box and box['width'] > 100 and box['height'] > 100:
                            thumbnail_img = img
                            break
                except Exception as e:
                    print(f"  Error finding thumbnail image: {e}")
        
        if not thumbnail_img:
            print("  Warning: Could not find thumbnail image, attempting screenshot of video area")
            # Take a screenshot of the video player area as fallback
            video_player = video_page.locator('[data-test-id="video-player-container"]').first
            if video_player.count() > 0:
                timestamp = int(time.time() * 1000)
                thumbnail_path = temp_dir / f"thumbnail_{timestamp}.png"
                video_player.screenshot(path=str(thumbnail_path))
                print(f"  Saved screenshot to {thumbnail_path}")
                return thumbnail_path
            else:
                raise Exception("Could not find video player for screenshot")
        
        # Screenshot the thumbnail
        timestamp = int(time.time() * 1000)
        thumbnail_path = temp_dir / f"thumbnail_{timestamp}.png"
        thumbnail_img.screenshot(path=str(thumbnail_path))
        print(f"  Saved thumbnail to {thumbnail_path}")
        
        return thumbnail_path
        
    finally:
        video_page.close()


def replace_link_with_thumbnail(page: Page, video_url: str, thumbnail_path: Path, thumbnail_width: int = 500):
    """Insert a clickable thumbnail after the video link in the TinyMCE editor."""
    print(f"  Inserting thumbnail after link (width: {thumbnail_width}px)...")
    
    # Get the editor iframe
    editor_frame = page.frame_locator('iframe[id^="id_questiontext_"]')

    # Find the link to get its text for alt text
    link = editor_frame.locator(f'a[href="{video_url}"]').first
    link_text = link.inner_text()

    # Don't delete anything yet - we'll do the replacement in source code mode
    # Just click somewhere in the editor to make sure it has focus
    print("  Inserting thumbnail image...")
    editor_frame.locator('body').click()
    
    # Click the Insert image button in TinyMCE toolbar
    # The button has aria-label="Image"
    page.click('button[aria-label="Image"]', timeout=5000)
    
    # Wait for the image dialog to appear
    page.wait_for_selector('text=Insert image', timeout=5000)
    time.sleep(1)
    
    # Set the file to upload directly without clicking anything
    # Find the file input element (it's there even if hidden)
    print("  Selecting file to upload...")
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(str(thumbnail_path))
    
    # Wait for upload to complete and Image details dialog to appear
    print("  Waiting for file upload and Image details dialog...")
    time.sleep(3)

    # The Image details dialog should now be visible
    # Wait for the modal dialog to appear
    try:
        # Wait for the modal dialog with title "Image details"
        page.wait_for_selector('.modal-dialog:has(.modal-title:has-text("Image details"))', timeout=10000)
        print("  Image details dialog appeared")

        # Find the alt text field (it's a textarea with class tiny_image_altentry)
        alttext_field = page.locator('textarea.tiny_image_altentry, #_tiny_image_altentry, textarea[name="altentry"]').first

        # Wait for it to be visible
        alttext_field.wait_for(state='visible', timeout=5000)

        # Create a description based on the link text
        video_name = link_text if link_text else "video"
        description = f"Thumbnail of {video_name}"

        # Fill in the alttext field
        alttext_field.fill(description)
        print(f"  Set image description to: {description}")

        # Set custom size
        print(f"  Setting custom size: {thumbnail_width}px width...")

        # Click the "Custom size" radio button
        custom_size_radio = page.locator('input.tiny_image_sizecustom, #_tiny_image_sizecustom').first
        custom_size_radio.click()
        time.sleep(0.3)

        # Check "Keep proportion" checkbox
        keep_proportion = page.locator('input.tiny_image_constrain, #_tiny_image_constrain').first
        if not keep_proportion.is_checked():
            keep_proportion.check()

        # Set the width
        width_input = page.locator('input.tiny_image_widthentry, #_tiny_image_widthentry').first
        width_input.fill(str(thumbnail_width))
        print(f"  Custom size set to {thumbnail_width}px width with proportions kept")

        # Click the Save button
        time.sleep(0.5)

        # Look for the Save button - it has class tiny_image_urlentrysubmit
        submit_clicked = False
        submit_selectors = [
            'button.tiny_image_urlentrysubmit',
            'button.btn-primary[type="submit"]',
            'button:has-text("Save")',
            '.modal-footer button[type="submit"]'
        ]

        for selector in submit_selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    print(f"  Clicking Save button: {selector}")
                    btn.click()
                    time.sleep(2)
                    submit_clicked = True
                    break
            except:
                continue

        if not submit_clicked:
            print("  Warning: Could not find Save button, trying Enter key...")
            page.keyboard.press('Enter')
            time.sleep(2)

    except Exception as e:
        print(f"  Error: Image details dialog did not appear: {e}")
        print("  This might cause issues with image insertion")
        # Don't try to click anything else - just wait and hope it works
        time.sleep(2)

    # Wait for the modal to close and image to be inserted
    print("  Waiting for modal to close and image to be inserted...")
    try:
        page.wait_for_selector('.modal-dialog', state='hidden', timeout=5000)
    except:
        pass
    time.sleep(1)

    # Now we need to make the image clickable by wrapping it in a link
    # Use TinyMCE JavaScript API for reliable editing
    print("  Using TinyMCE API to wrap image with link...")

    try:
        # Find the TinyMCE editor instance for questiontext
        # First, get the editor ID by finding the iframe
        editor_id = page.evaluate('''() => {
            const iframe = document.querySelector('iframe[id^="id_questiontext_"]');
            if (iframe) {
                // The editor ID is usually the iframe ID without the _ifr suffix
                return iframe.id.replace('_ifr', '');
            }
            return null;
        }''')

        if not editor_id:
            raise Exception("Could not find TinyMCE editor ID")

        print(f"  Found TinyMCE editor: {editor_id}")

        # Get current HTML content from TinyMCE editor
        html_content = page.evaluate(f'''() => {{
            const editor = tinymce.get('{editor_id}');
            if (editor) {{
                return editor.getContent();
            }}
            return null;
        }}''')

        if not html_content:
            raise Exception("Could not get HTML content from TinyMCE editor")

        print("  Got HTML content from TinyMCE")

        # Find the new image tag we just inserted
        img_pattern = r'<img[^>]*src="[^"]*' + re.escape(thumbnail_path.name) + r'"[^>]*>'
        img_matches = list(re.finditer(img_pattern, html_content))

        # Find the old link tag to replace
        # Escape the URL for use in regex
        escaped_url = re.escape(video_url)
        link_pattern = r'<a[^>]*href="' + escaped_url + r'"[^>]*>.*?</a>'
        link_matches = list(re.finditer(link_pattern, html_content, re.DOTALL))

        if img_matches and link_matches:
            # Get the last image (most recently inserted)
            last_img_match = img_matches[-1]
            img_tag = last_img_match.group(0)

            # First, remove the standalone image
            html_without_standalone_img = html_content[:last_img_match.start()] + html_content[last_img_match.end():]

            # Find the link again in the modified HTML (indices have changed)
            link_match_new = re.search(link_pattern, html_without_standalone_img, re.DOTALL)

            if link_match_new:
                # Find the end of the sentence after the link (look for period/full-stop)
                # Search for a period after the link ends
                # Period followed by space, closing tag, or opening tag (like <br>)
                sentence_end_pattern = r'\.(\s|<)'
                search_start = link_match_new.end()
                sentence_end_match = re.search(sentence_end_pattern, html_without_standalone_img[search_start:])

                # Create the wrapped image with line breaks and security attributes
                wrapped_img = f'<br><a href="{video_url}" target="_blank" rel="noopener">{img_tag}</a><br>'

                if sentence_end_match:
                    # Found the period - insert after it
                    insertion_point = search_start + sentence_end_match.start() + 1  # +1 to be after the period

                    # Insert the thumbnail after the sentence
                    new_html = (html_without_standalone_img[:insertion_point] +
                               wrapped_img +
                               html_without_standalone_img[insertion_point:])
                else:
                    # No period found - insert at the very end of the question text
                    new_html = html_without_standalone_img + wrapped_img
            else:
                # Fallback: if we can't find the link, just remove the standalone image
                new_html = html_without_standalone_img

            # Update TinyMCE editor content using JavaScript API
            # Escape the HTML for JavaScript string
            escaped_html = new_html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')

            page.evaluate(f'''() => {{
                const editor = tinymce.get('{editor_id}');
                if (editor) {{
                    editor.setContent('{escaped_html}');
                }}
            }}''')

            print(f"  Replaced old link with clickable thumbnail in HTML")
            time.sleep(0.5)

            print("  Successfully replaced link with clickable thumbnail!")
        elif img_matches and not link_matches:
            # No link found, just wrap the image
            print("  Warning: Could not find old link, will just add image with link")
            last_img_match = img_matches[-1]
            img_tag = last_img_match.group(0)
            wrapped_img = f'<a href="{video_url}" target="_blank" rel="noopener">{img_tag}</a>'
            new_html = html_content[:last_img_match.start()] + wrapped_img + html_content[last_img_match.end():]

            # Escape the HTML for JavaScript string
            escaped_html = new_html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')

            page.evaluate(f'''() => {{
                const editor = tinymce.get('{editor_id}');
                if (editor) {{
                    editor.setContent('{escaped_html}');
                }}
            }}''')

            time.sleep(0.5)
        else:
            print(f"  Warning: Could not find the inserted image in HTML (looking for {thumbnail_path.name})")

    except Exception as e:
        print(f"  Error using TinyMCE API to wrap image: {e}")
        raise


def save_question_changes(page: Page):
    """Save the changes to the question."""
    print("  Saving question changes...")
    
    # Scroll to bottom to ensure Save button is visible
    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    time.sleep(0.5)
    
    # Click Save changes button
    page.click('input[type="submit"][value*="Save"], button:has-text("Save changes")')
    
    # Wait for save to complete
    page.wait_for_load_state('networkidle')
    print("  Question saved successfully!")


def process_question(page: Page, question_element, temp_dir: Path, debug: bool = False, ms_name: str = None, ms_password: str = None, is_first_question: bool = False, thumbnail_width: int = 250):
    """Process a single description question."""
    # Extract question name for logging
    question_name = question_element.locator('.questionname').inner_text()
    print(f"\nProcessing question: {question_name}")
    
    # Get the edit link
    edit_url = extract_edit_link(question_element)
    print(f"  Edit URL: {edit_url}")
    
    # Navigate to edit page
    page.goto(edit_url, wait_until='networkidle')
    time.sleep(2)
    
    # Find all video links in the editor
    video_urls = find_video_links_in_editor(page)
    
    if not video_urls:
        print("  No video links found in this question, skipping...")
        return
    
    # Process each video link
    for i, video_url in enumerate(video_urls, 1):
        print(f"\n  Processing video {i}/{len(video_urls)}...")
        
        # First video of first question needs MS auth
        first_video = (is_first_question and i == 1)
        
        try:
            # Download thumbnail
            thumbnail_path = download_video_thumbnail(page, video_url, temp_dir, debug, ms_name, ms_password, first_video)
            
            # Replace link with thumbnail
            replace_link_with_thumbnail(page, video_url, thumbnail_path, thumbnail_width)
            
        except Exception as e:
            print(f"  Error processing video {video_url}: {e}")
            print("  Skipping this video and continuing...")
            continue
    
    # Save the question changes
    save_question_changes(page)


def main():
    parser = argparse.ArgumentParser(
        description='Replace video links with thumbnails in Moodle quiz questions'
    )
    parser.add_argument('quiz_url', help='URL of the Moodle quiz')
    parser.add_argument('username', help='Moodle username')
    parser.add_argument('password', help='Moodle password')
    parser.add_argument('--name', help='Full name for Microsoft authentication (if different from username)')
    parser.add_argument('--thumbnail-width', type=int, default=500,
                        help='Width of thumbnail images in pixels (default: 500)')
    parser.add_argument('--headless', action='store_true',
                        help='Run browser in headless mode (default: visible)')
    parser.add_argument('--debug', action='store_true',
                        help='Pause before thumbnail extraction to allow manual inspection')

    args = parser.parse_args()
    
    # Create temporary directory for thumbnails
    temp_dir = Path('/tmp/moodle_thumbnails')
    temp_dir.mkdir(exist_ok=True)
    
    print("Starting Moodle Video Thumbnail Replacer...")
    print(f"Quiz URL: {args.quiz_url}")
    print(f"Username: {args.username}")
    print(f"Temporary directory: {temp_dir}")
    print()
    
    with sync_playwright() as p:
        # Launch browser - use Chrome channel for better SharePoint/Stream support
        # Chromium often has issues with Microsoft video DRM and codecs
        print("Launching browser (using Chrome for SharePoint compatibility)...")
        try:
            # Try to use Chrome first
            browser = p.chromium.launch(
                channel="chrome",
                headless=args.headless
            )
        except Exception as e:
            print(f"Could not launch Chrome: {e}")
            print("Trying Edge instead...")
            try:
                # Try Edge as fallback (also good for Microsoft services)
                browser = p.chromium.launch(
                    channel="msedge",
                    headless=args.headless
                )
            except Exception as e2:
                print(f"Could not launch Edge: {e2}")
                print("Falling back to standard Chromium (may have video playback issues)...")
                browser = p.chromium.launch(headless=args.headless)
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            # Navigate to quiz URL
            print(f"Navigating to {args.quiz_url}...")
            page.goto(args.quiz_url, wait_until='networkidle')
            
            # Check if we were redirected to login
            if '/login/index.php' in page.url:
                print("Redirected to login page")
                login_to_moodle(page, args.username, args.password)
                
                # Navigate to the quiz page again after login
                print(f"Navigating back to quiz: {args.quiz_url}")
                page.goto(args.quiz_url, wait_until='networkidle')
            else:
                # Try to login if we see a login form
                if page.locator('input[name="username"]').count() > 0:
                    login_to_moodle(page, args.username, args.password)
                else:
                    print("Already logged in or no login required")
            
            # Click Questions link
            click_questions_link(page)
            
            # Get all description questions
            questions = get_description_questions(page)
            
            if not questions:
                print("No description questions found!")
                return
            
            # Process each question
            # Use provided name or fallback to username for MS auth
            ms_name = args.name if args.name else args.username
            
            for i, question in enumerate(questions, 1):
                print(f"\n{'='*60}")
                print(f"Question {i}/{len(questions)}")
                print(f"{'='*60}")
                
                is_first_question = (i == 1)
                
                try:
                    process_question(page, question, temp_dir, args.debug, ms_name, args.password, is_first_question, args.thumbnail_width)
                except Exception as e:
                    print(f"Error processing question: {e}")
                    print("Continuing with next question...")
                    
                    # Navigate back to questions page
                    click_questions_link(page)
                    # Re-get questions list as DOM might have changed
                    questions = get_description_questions(page)
            
            print("\n" + "="*60)
            print("All questions processed successfully!")
            print("="*60)
            
        except Exception as e:
            print(f"\nFatal error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Keep browser open for a moment to see results
            if not args.headless:
                print("\nPress Enter to close browser...")
                input()
            
            browser.close()


if __name__ == '__main__':
    main()
