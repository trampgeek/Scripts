# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains `moodle_video_thumbnail_replacer.py`, a Python automation script that replaces video links in Moodle quiz description questions with clickable thumbnails extracted from SharePoint/Microsoft Stream videos.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (Chrome recommended for SharePoint compatibility)
playwright install chrome

# Alternative browsers (less reliable for SharePoint/Stream)
playwright install msedge
playwright install chromium
```

### Running the Script
```bash
# Basic usage
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password>

# With Microsoft authentication (if name differs from username)
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --name "Full Name"

# Custom thumbnail width (default is 250px)
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --thumbnail-width 300

# Headless mode
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --headless

# Debug mode (pauses for manual inspection)
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --debug
```

## Architecture

### Main Workflow
The script follows a multi-step automation process:

1. **Authentication** (`login_to_moodle`) - Logs into Moodle using provided credentials
2. **Navigation** (`click_questions_link`) - Opens the quiz questions view
3. **Question Discovery** (`get_description_questions`) - Finds all description-type questions (li.qtype_description)
4. **Per-Question Processing** (`process_question`):
   - Opens question editor
   - Finds video links (`find_video_links_in_editor`) matching `/mod/url/view.php` pattern
   - For each video:
     - Downloads thumbnail (`download_video_thumbnail`)
     - Replaces text link with clickable image (`replace_link_with_thumbnail`)
   - Saves changes (`save_question_changes`)

### Browser Automation Details

**Browser Selection** (lines 660-682): The script tries Chrome first, falls back to Edge, then Chromium. This is critical because SharePoint/Microsoft Stream videos require proprietary codecs and DRM support that Chromium lacks.

**Microsoft Authentication** (lines 163-200): Only the first video requires authentication. The script:
- Fills in name/email and password fields
- Waits up to 60 seconds for the "Stay signed in?" page to appear (polling, not sleeping)
- Auto-clicks "Yes" on "Stay signed in?" prompt (button id="idSIButton9[value='Yes']")
- Handles various fallback selectors if the primary method fails

**TinyMCE Editor Interaction**:
- Editor content is in an iframe (`iframe[id^="id_questiontext_"]`)
- Image insertion uses the `button[aria-label="Image"]` toolbar button
- File uploads use hidden `input[type="file"]` elements
- Multiple editors exist on the page (`#fitem_id_questiontext` and `#fitem_id_generalfeedback`) - selectors must be scoped appropriately
- HTML manipulation uses TinyMCE JavaScript API (`tinymce.get(editor_id).getContent()` and `.setContent()`)
- Editor ID is derived from the iframe ID by removing the `_ifr` suffix

**Link Filtering**: Only processes links that lead to actual video pages:
- After navigating to a link, checks if URL contains 'stream.aspx'
- Skips links that don't lead to SharePoint/Stream videos (e.g., lecture notes, index pages)

**Thumbnail Extraction**: Multi-method approach:
1. Opens Video settings panel (`button[aria-label="Video settings"]`)
2. Clicks Thumbnail option (tries 4 different selectors)
3. Searches for thumbnail in `#CollapsibleCustomOptions` with blob URLs (`img[src^="blob:"]`)
4. Falls back to main page images with various selectors
5. Final fallback: video player screenshot

### Key Technical Considerations

**Timeout Management**: The script uses a mix of Playwright `wait_for_selector` with explicit timeouts and `time.sleep()` calls. Many operations wait for `networkidle` to ensure pages fully load.

**Error Recovery**: Each video processing is wrapped in try-except to continue with remaining videos if one fails. Questions are processed sequentially with similar error handling.

**Temporary Files**: Thumbnails are saved to `/tmp/moodle_thumbnails/` with timestamp-based filenames (`thumbnail_{timestamp}.png`).

**DOM Structure Dependencies**: The script is tightly coupled to:
- Moodle's quiz question page structure (li.qtype_description)
- TinyMCE editor iframe naming convention
- SharePoint Video settings UI structure
- Microsoft authentication flow

## Important Notes

- The script must have edit permissions for the target quiz
- Only processes description-type questions
- First video access requires MFA approval (30-second wait)
- Chrome or Edge browser is essential for SharePoint video playback
- Thumbnails persist in `/tmp/moodle_thumbnails/` after execution
