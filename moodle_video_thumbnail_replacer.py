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
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError


class NotAVideo (Exception):
    pass

class QuizVideoLinkReplacer():

    def __init__(self, args, temp_dir):
        self.quiz_url = args.quiz_url
        self.username = args.username
        self.password = args.password
        self.ms_email = args.ms_email
        self.headless = args.headless
        self.thumbnail_width = args.thumbnail_width
        self.question_name = args.question_name
        self.temp_dir = temp_dir
        self.page = None


    def replace_all_video_links(self):
        with sync_playwright() as p:
                # Launch browser - use Chrome channel for better SharePoint/Stream support
                # Chromium often has issues with Microsoft video DRM and codecs
                print("Launching browser (using Chrome for SharePoint compatibility)...")
                try:
                    # Try to use Chrome.
                    browser = p.chromium.launch(
                        channel="chrome",
                        headless=self.headless
                    )
                except Exception as e:
                    print(f"Could not launch Chrome: {e}\nAborting.")
                    sys.exit(0)
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080}
                )
                self.page = context.new_page()
                
                try:
                    self.process_quiz()
                    
                except Exception as e:
                    print(f"\nFatal error: {e}")
                    import traceback
                    traceback.print_exc()
                    
                finally:
                    # Keep browser open for a moment to see results
                    if not self.headless:
                        print("\nPress Enter to close browser...")
                        input()
                    
                    browser.close()

    def login_to_moodle(self, page: Page):
        """Login to Moodle using saved credentials."""
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
        page.fill('input[name="username"]', self.username)
        page.fill('input[name="password"]', self.password)
        
        # Submit the form
        print("  Submitting login form...")
        page.click('button[type="submit"], input[type="submit"]')
        
        # Wait for login to complete
        page.wait_for_load_state('networkidle')
        print("Successfully logged in!")


    def process_quiz(self):
        """Navigate to and process the given quiz"""
        self.navigate_to_quiz()
 
        self.click_questions_link()
 
        questions = self.get_description_questions()

        if not questions:
            print("No description questions found!")
            return

        # Filter to specific question if question_name is provided
        if self.question_name:
            filtered_questions = []
            for question in questions:
                q_name = question.locator('.questionname').inner_text()
                if q_name == self.question_name:
                    filtered_questions.append(question)
                    break

            if not filtered_questions:
                print(f"Question '{self.question_name}' not found!")
                return

            questions = filtered_questions
            print(f"Filtering to process only question: {self.question_name}")

        # Process each question

        for i, question in enumerate(questions, 1):
            print(f"\n{'='*60}")
            print(f"Question {i}/{len(questions)}")
            print(f"{'='*60}")

            is_first_question = (i == 1)
            
            try:
                self.process_question(question, is_first_question)
            except Exception as e:
                print(f"Error processing question: {e}")
                print("Continuing with next question...")
                
            # Navigate back to questions page
            self.click_questions_link()
            # Re-get questions list as DOM might have changed
            questions = self.get_description_questions()
        
        print("\n" + "="*60)
        print("All questions processed successfully!")
        print("="*60)


    def navigate_to_quiz(self):
        """Like it says"""
        print(f"Navigating to {self.quiz_url}...")
        self.page.goto(self.quiz_url, wait_until='networkidle')
        
        # Check if we were redirected to login
        if '/login/index.php' in self.page.url:
            print("Redirected to login page")
            self.login_to_moodle(self.page)
            
            # Navigate to the quiz page again after login
            print(f"Navigating back to quiz: {self.quiz_url}")
            self.page.goto(self.quiz_url, wait_until='networkidle')
        else:
            # Try to login if we see a login form
            if self.page.locator('input[name="username"]').count() > 0:
                self.login_to_moodle(self.page)
            else:
                print("Already logged in or no login required")


    def click_questions_link(self):
        """Click the Questions link to see all quiz questions."""
        print("Navigating to Questions view...")
        
        # Look for "Questions" link - be specific to avoid clicking wrong links
        try:
            # First try: link with "Questions" text and href containing "mod/quiz/edit.php"
            self.page.click('a[href*="/mod/quiz/edit.php"]:has-text("Questions")', timeout=5000)
        except PlaywrightTimeoutError:
            try:
                # Second try: any link with exact text "Questions"
                questions_links = self.page.locator('a:has-text("Questions")').all()
                for link in questions_links:
                    href = link.get_attribute('href')
                    if href and '/mod/quiz/edit.php' in href:
                        link.click()
                        break
            except:
                # Last resort: just click first Questions link
                self.page.click('a:has-text("Questions")')
        
        self.page.wait_for_load_state('networkidle')
        print("Questions page loaded")


    def get_description_questions(self) -> list:
        """Get all description type questions from the quiz."""
        print("Finding description questions...")
        
        # Find all li elements with class qtype_description
        questions = self.page.locator('li.qtype_description').all()
        print(f"Found {len(questions)} description question(s)")
        
        return questions


    def extract_edit_link(self, question_element) -> str:
        """Extract the edit link from a question element."""
        # Find the edit link within the question
        edit_link = question_element.locator('a[title*="Edit question"]').get_attribute('href')
        return edit_link


    def find_video_links_in_editor(self) -> list:
        """Find all video links in the TinyMCE editor (including those with existing thumbnails)."""
        print("  Finding video links in question content...")

        # Wait for TinyMCE editor to load
        self.page.wait_for_selector('.tox-tinymce', timeout=10000)

        # Get the editor iframe
        editor_frame = self.page.frame_locator('iframe[id^="id_questiontext_"]')

        # Find all links that match the pattern
        links = editor_frame.locator('a[href*="/mod/url/view.php"]').all()

        # Collect all unique URLs in document order
        seen_urls = set()
        urls_in_order = []

        for link in links:
            href = link.get_attribute('href')
            if href and href not in seen_urls:
                seen_urls.add(href)
                urls_in_order.append(href)

        print(f"  Found {len(urls_in_order)} unique video link(s)")
        return urls_in_order


    def download_video_thumbnail(self, video_url: str, first_video: bool = False) -> Path:
        """
        Navigate to the video URL, extract thumbnail, and save it.
        Returns the path to the saved thumbnail.
        """
        print(f"  Processing link: {video_url}")
        
        # Open video URL in new tab
        context = self.page.context
        video_page = context.new_page()
        
        try:
            # Use 'load' instead of 'networkidle' for SharePoint/Stream pages
            # These pages have constant network activity (video streams, analytics, etc.)
            video_page.goto(video_url, wait_until='load', timeout=30000)

            # Brief wait for potential redirects to SharePoint
            time.sleep(1)
            
            # Handle Microsoft authentication if this is the first URL.
            if first_video:
                print("  Handling Microsoft authentication...")
                
                # Check if we're on Microsoft login page
                if 'login.microsoftonline.com' in video_page.url or 'login.windows.net' in video_page.url:
                    try:
                        # Wait for and fill in name/email field
                        print("  Filling in name/email...")
                        name_input = video_page.locator('input[type="email"], input[name="loginfmt"]')
                        if name_input.count() > 0:
                            name_input.fill(self.ms_email)
                            video_page.click('input[type="submit"], button[type="submit"]')
                            video_page.wait_for_load_state('load')

                        # Fill in password
                        print("  Filling in password...")
                        password_input = video_page.locator('input[type="password"], input[name="passwd"]')
                        if password_input.count() > 0:
                            password_input.fill(self.password)
                            video_page.click('input[type="submit"], button[type="submit"]')
                            video_page.wait_for_load_state('load')
                        
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

                            # The Yes button has id="idSIButton9" on the Stay signed in page
                            yes_button = video_page.locator('#idSIButton9[value="Yes"]')
                            if yes_button.count() > 0 and yes_button.is_visible():
                                print("  Found 'Yes' button, clicking to stay signed in...")
                                yes_button.click()
                                video_page.wait_for_load_state('load')
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
                                        video_page.wait_for_load_state('load')
                                        break

                        except Exception as e:
                            print(f"  No 'Stay signed in' prompt appeared within 60 seconds (this is OK): {e}")

                        # Wait for redirect to SharePoint
                        video_page.wait_for_load_state('load', timeout=10000)
                        print("  Microsoft authentication completed!")
                        
                    except Exception as e:
                        print(f"  Warning during Microsoft authentication: {e}")
                        print("  Attempting to continue...")
            
            # Check if this is actually a video link (must contain 'stream.aspx')
            current_url = video_page.url
            if 'stream.aspx' not in current_url:
                print(f"  Skipping - not a video link (URL: {current_url})")
                raise NotAVideo(f"Not a video link - URL does not contain 'stream.aspx': {current_url}")

            print("  Confirmed video link (stream.aspx found)")

            # Wait for and click Video settings button
            print("  Opening Video settings panel...")
            try:
                video_settings_button = video_page.locator('button[aria-label="Video settings"]')
                video_settings_button.wait_for(state='visible', timeout=10000)
                print("  Found Video settings button, clicking...")
                video_settings_button.click()
            except Exception as e:
                print(f"  Could not click Video settings: {e}")
                print("  Panel might already be open or have different structure")

            # Click the Thumbnail option
            print("  Clicking Thumbnail option...")
            thumbnail_button = video_page.locator('button[aria-label="Thumbnail"]')
            thumbnail_button.wait_for(state='visible', timeout=5000)
            print("  Found Thumbnail button by aria-label...")
            thumbnail_button.first.click()

            # Wait for thumbnail image to appear and get it
            print("  Waiting for thumbnail to load...")
            blob_img = video_page.locator('#CollapsibleCustomOptions img[src^="blob:"]').first
            blob_img.wait_for(state='visible', timeout=5000)

            if blob_img.count() == 0:
                raise Exception("Could not find blob thumbnail in CollapsibleCustomOptions")

            blob_url = blob_img.get_attribute('src')
            print(f"  Found blob thumbnail: {blob_url[:60] if blob_url else 'N/A'}...")

            # Download the blob data at full resolution using JavaScript
            timestamp = int(time.time() * 1000)
            thumbnail_path = self.temp_dir / f"thumbnail_{timestamp}.png"

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
            
        finally:
            video_page.close()


    def add_thumbnail_after_link(self, video_url: str, thumbnail_path: Path):
        """Insert a clickable thumbnail following the period at the end of the 
           sentence containing the given video_url.
           This is a bit tricky. We first insert the image at the end of the
           question text using the TinyMCE "Insert image" toolbar function,
           then switch to using the TinyMCE edit API to move the image to
           the right place and wrap it in an <a> element.
        """
        
        # Get the editor iframe (NB: assuming use of TinyMCE editor).
        editor_frame = self.page.frame_locator('iframe[id^="id_questiontext_"]')

        # Find the link to get its text for alt text
        link = editor_frame.locator(f'a[href="{video_url}"]').first
        link_text = link.inner_text()

        # Don't delete anything yet - we'll do the replacement in source code mode
        # Click at a safe location in the editor to give it focus, ensuring we don't
        # click on an existing image (which would cause TinyMCE to open Edit mode instead of Insert)
        print("  Inserting the thumbnail image...")
        # Click at the very start of the body content to avoid clicking on any images
        editor_frame.locator('body').click(position={'x': 5, 'y': 5})
        
        # Click the Insert image button in TinyMCE toolbar
        # The button has aria-label="Image"
        self.page.click('button[aria-label="Image"]', timeout=5000)

        # Wait for the "Insert image" dialog to appear
        # If this fails, it likely means we accidentally clicked on an existing image,
        # causing TinyMCE to open the edit dialog instead of insert dialog
        try:
            self.page.wait_for_selector('text=Insert image', timeout=5000)
        except Exception as e:
            raise Exception(
                "Failed to open Insert image dialog. This likely means the editor focus "
                "was on an existing image, causing TinyMCE to open Edit mode instead of Insert mode. "
                f"Original error: {e}"
            )

        # Set the file to upload directly without clicking anything
        # Find the file input element (it's there even if hidden)
        print("  Selecting file to upload...")
        file_input = self.page.locator('input[type="file"]').first
        file_input.set_input_files(str(thumbnail_path))
        
        # Wait for the modal Image details dialog to appear
        try:
            # Wait for the modal dialog with title "Image details"
            self.page.wait_for_selector('.modal-dialog:has(.modal-title:has-text("Image details"))', timeout=10000)
            print("  Image details dialog appeared")

            self.set_image_details_and_save(link_text)

        except Exception as e:
            print(f"  Error: Image details dialog did not appear: {e}")

        # Wait for the modal to close and image to be inserted
        print("  Waiting for modal to close and image to be inserted...")
        self.page.wait_for_selector('.modal-dialog', state='hidden', timeout=5000)


        # Now we need to make the image clickable by wrapping it in a link
        self.move_image_and_wrap_in_link(video_url, thumbnail_path)


    def set_image_details_and_save(self, link_text):
        """Fill out the Image details dialog and save.
           Called after Image Details modal dialog has appeared.
        """
        # Find the alt text field and fill it in.
        alttext_field = self.page.locator('textarea.tiny_image_altentry, #_tiny_image_altentry, textarea[name="altentry"]').first
        alttext_field.wait_for(state='visible', timeout=5000)
        video_name = link_text if link_text else "video"
        description = f"Thumbnail of {video_name}"
        alttext_field.fill(description)
        print(f"  Set image description to: {description}")

        # Set custom size. Try Moodle 5 approach first (Custom button with class image-custom-size-toggle)
        print(f"  Setting custom size: {self.thumbnail_width}px width...")
        custom_button = self.page.locator('button.image-custom-size-toggle').first
        if custom_button.count() > 0:
            print("  Using Moodle 5 Custom button...")
            custom_button.click()
        else:
            # Fall back to Moodle 4 approach (Custom size radio button + Keep proportion)
            print("  Using Moodle 4 Custom size radio button...")
            custom_size_radio = self.page.locator('input.tiny_image_sizecustom, #_tiny_image_sizecustom').first
            custom_size_radio.click()

            # Check "Keep proportion" checkbox.
            keep_proportion = self.page.locator('input.tiny_image_constrain, #_tiny_image_constrain').first
            if not keep_proportion.is_checked():
                keep_proportion.check()

        # Set the width (same for both Moodle 4 and 5)
        width_input = self.page.locator('input.tiny_image_widthentry, #_tiny_image_widthentry').first
        width_input.fill(str(self.thumbnail_width))
        print(f"  Custom size set to {self.thumbnail_width}px width")

        # Look for the Save button - it has class tiny_image_urlentrysubmit
        submit_clicked = False
        submit_selector = 'button.tiny_image_urlentrysubmit'

        try:
            btn = self.page.locator(submit_selector).first
            print(f"  Button locator count: {btn.count()}")
            print(f"  Button is_visible: {btn.is_visible() if btn.count() > 0 else 'N/A'}")
            if btn.count() > 0 and btn.is_visible():
                print(f"  Clicking Save button: {submit_selector}")
                time.sleep(1)
                btn.click()
                submit_clicked = True
                print("  Save button click completed")
        except Exception as e:
            print(f"  Exception clicking Save button: {e}")
            import traceback
            traceback.print_exc()

        if not submit_clicked:
            print("  Warning: Could not find Save button")


    def move_image_and_wrap_in_link(self, video_url: str, thumbnail_path: Path):
        """Use the TinyMCE edit API to edit the question text.
           Remove any existing thumbnails with the given video_url.
           Then locate the thumbnail we just added, wrap it in an <a> link,
           and insert it after the first period following the first occurrence
           of the video url.
        """
        print("  Using TinyMCE API to wrap image with link...")

        try:
            # Find the TinyMCE editor instance for questiontext
            editor_id = self.page.evaluate('''() => {
                const iframe = document.querySelector('iframe[id^="id_questiontext_"]');
                if (iframe) {
                    return iframe.id.replace('_ifr', '');
                }
                return null;
            }''')

            if not editor_id:
                raise Exception("Could not find TinyMCE editor ID")

            print(f"  Found TinyMCE editor: {editor_id}")

            # Get current HTML content from TinyMCE editor
            html_content = self.page.evaluate(f'''() => {{
                const editor = tinymce.get('{editor_id}');
                if (editor) {{
                    return editor.getContent();
                }}
                return null;
            }}''')

            if not html_content:
                raise Exception("Could not get HTML content from TinyMCE editor")

            print("  Got HTML content from TinyMCE")

            # Step 1: Remove any existing wrapped_img structure for this video_url
            # The wrapped_img structure is: (optional <br>)<a href="video_url" ...><span ...><img ...><img ...></span></a>(optional <br>)
            escaped_url = re.escape(video_url)
            # Make both leading and trailing <br> optional, and match <a> tags that contain <span> wrappers
            existing_thumbnail_pattern = r'(?:<br>\s*)?<a[^>]*href="' + escaped_url + r'"[^>]*>\s*<span[^>]*>.*?</span>\s*</a>\s*(?:<br>)?'
            old_count = len(html_content)
            html_content = re.sub(existing_thumbnail_pattern, '', html_content, flags=re.DOTALL)
            if old_count != len(html_content):
                print("  Removed existing thumbnail for this video")

            # Step 2: Locate and extract the <img> element with the given thumbnail path
            img_pattern = r'<img[^>]*src="[^"]*' + re.escape(thumbnail_path.name) + r'"[^>]*>'
            img_match = re.search(img_pattern, html_content)

            if not img_match:
                print(f"  Warning: Could not find the inserted image in HTML (looking for {thumbnail_path.name})")
                return

            img_tag = img_match.group(0)
            # Remove the image from its current location
            html_content = html_content[:img_match.start()] + html_content[img_match.end():]

            # Step 3: Wrap it into an <a> element with play icon overlay
            play_icon = '<img src="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 64 64\'%3E%3Ccircle cx=\'32\' cy=\'32\' r=\'32\' fill=\'rgba(0,0,0,0.6)\'/%3E%3Cpath d=\'M 26 20 L 26 44 L 44 32 Z\' fill=\'white\'/%3E%3C/svg%3E" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:64px;height:64px;pointer-events:none;" alt="">'
            wrapped_img = f'<br><a href="{video_url}" target="_blank" rel="noopener" style="text-decoration:none;"><span style="position:relative;display:inline-block;">{img_tag}{play_icon}</span></a><br>'

            # Step 4: Insert after the first period following the first occurrence of video_url
            url_pos = html_content.find(video_url)

            if url_pos == -1:
                # No URL found, append at the end
                print("  Warning: Could not find video URL in HTML, appending thumbnail at end")
                new_html = html_content + wrapped_img
            else:
                # Find the first period after the URL occurrence
                period_pattern = r'\.(\s|<)'
                period_match = re.search(period_pattern, html_content[url_pos:])

                if period_match:
                    # Insert after the period
                    insertion_point = url_pos + period_match.start() + 1  # +1 to be after the period
                    new_html = html_content[:insertion_point] + wrapped_img + html_content[insertion_point:]
                else:
                    # No period found, append at the end
                    print("  Warning: Could not find period after video URL, appending thumbnail at end")
                    new_html = html_content + wrapped_img

            # Update TinyMCE editor content
            escaped_html = new_html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')

            self.page.evaluate(f'''() => {{
                const editor = tinymce.get('{editor_id}');
                if (editor) {{
                    editor.setContent('{escaped_html}');
                }}
            }}''')

            print("  Successfully replaced link with clickable thumbnail!")

        except Exception as e:
            print(f"  Error using TinyMCE API to wrap image: {e}")
            raise
    

    def save_question_changes(self):
        """Save the changes to the question."""
        print("  Saving question changes...")

        # Scroll to bottom to ensure Save button is visible
        self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

        # Click Save changes button
        self.page.click('input[type="submit"][value*="Save"], button:has-text("Save changes")')
        
        # Wait for save to complete
        self.page.wait_for_load_state('networkidle')
        print("  Question saved successfully!")


    def process_question(self, question_element, is_first_question: bool = False):
        """Process a single description question."""
        # Extract question name for logging
        question_name = question_element.locator('.questionname').inner_text()
        print(f"\nProcessing question: {question_name}")
        
        # Get the edit link
        edit_url = self.extract_edit_link(question_element)
        print(f"  Edit URL: {edit_url}")
        
        # Navigate to edit page
        # Use 'domcontentloaded' instead of 'networkidle' to avoid hanging on pages
        # with embedded content (PowerPoint, videos, etc.) that keep network active
        self.page.goto(edit_url, wait_until='domcontentloaded')
        
        # Find all video links in the editor
        video_urls = self.find_video_links_in_editor()

        if not video_urls:
            print("  No likely video links found in this question, skipping...")
            # Navigate back to questions page before returning
            self.click_questions_link()
            return

        # Process videos in reverse order to maintain correct document order
        # (each insertion at same position naturally reverses order)
        video_urls.reverse()

        # Process each video link
        for i, video_url in enumerate(video_urls, 1):
            print(f"\n  Processing link {i}/{len(video_urls)}...")
            
            # First video of first question needs MS auth
            first_video = (is_first_question and i == 1)
            
            try:
                # Download thumbnail
                thumbnail_path = self.download_video_thumbnail(video_url, first_video)
                
                # Add the thumbnail at the end of the sentence containing the video URL.
                self.add_thumbnail_after_link(video_url, thumbnail_path)
                
            except NotAVideo:
                continue
            
            except Exception as e:
                print(f"  Error processing link {video_url}: {e}")
                print("  Skipping this video and continuing...")
                continue
        
        # Save the question changes
        self.save_question_changes()


def main():
    parser = argparse.ArgumentParser(
        description='Replace video links with thumbnails in Moodle quiz questions'
    )
    parser.add_argument('quiz_url', help='URL of the Moodle quiz')
    parser.add_argument('username', help='Moodle username')
    parser.add_argument('password', help='Moodle password')
    parser.add_argument('ms_email', help='Full email for Microsoft authentication')
    parser.add_argument('--thumbnail-width', type=int, default=250,
                        help='Width of thumbnail images in pixels (default: 250)')
    parser.add_argument('--question-name', type=str, default=None,
                        help='Process only the question with this name (default: process all questions)')
    parser.add_argument('--headless', action='store_true',
                        help='Run browser in headless mode (default: visible)')

    args = parser.parse_args()
    
    # Create temporary directory for thumbnails
    temp_dir = Path('/tmp/moodle_thumbnails')
    temp_dir.mkdir(exist_ok=True)
    
    print("Starting Moodle Video Thumbnail Replacer...")
    print(f"Quiz URL: {args.quiz_url}")
    print(f"Username: {args.username}")
    print(f"Temporary directory: {temp_dir}")
    print()
    
    replacer = QuizVideoLinkReplacer(args, temp_dir)
    replacer.replace_all_video_links()


if __name__ == '__main__':
    main()
