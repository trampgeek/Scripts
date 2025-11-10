# Moodle Video Thumbnail Replacer

A Python script that automates replacing video links in Moodle quiz description questions with clickable thumbnails from SharePoint/Microsoft Stream videos.

## Features

- Logs into Moodle with AD authentication
- Finds all description-type questions in a quiz
- Extracts video thumbnails from SharePoint/Stream videos
- Replaces text links with clickable image thumbnails
- Processes multiple videos per question
- Handles multiple questions in batch

## Requirements

- Python 3.7+
- Playwright

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
# Install Chromium (basic - may have issues with SharePoint videos)
playwright install chromium

# RECOMMENDED: Install Chrome for better SharePoint/Stream support
playwright install chrome

# OR install Edge (also works well with Microsoft services)
playwright install msedge
```

**Important**: The script works best with Chrome or Edge browsers due to SharePoint/Microsoft Stream video codec requirements. Chromium (the open-source version) often fails to play these videos due to missing proprietary codecs and DRM support.

## Usage

Basic usage:
```bash
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password>
```

With Microsoft authentication (different name from username):
```bash
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --name "Your Full Name"
```

Custom thumbnail width (default is 250px):
```bash
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --thumbnail-width 300
```

Run in headless mode (no visible browser):
```bash
python moodle_video_thumbnail_replacer.py <quiz_url> <username> <password> --headless
```

### Example

```bash
python moodle_video_thumbnail_replacer.py \
    "https://quiz2025.csse.canterbury.ac.nz/mod/quiz/view.php?id=3468" \
    "abc123" \
    "mypassword" \
    --name "John Smith"
```

### Microsoft Authentication

The first video accessed will require Microsoft/SharePoint authentication:
1. **Name/Email**: Use `--name` parameter if different from your Moodle username
2. **Password**: Same as Moodle password
3. **MFA**: Script will pause for 30 seconds - approve the sign-in on your device
4. **Stay Signed In**: Script automatically clicks "Yes"

Subsequent videos will not require re-authentication.

## How It Works

1. **Login**: Authenticates to Moodle using provided credentials
2. **Navigate**: Opens the quiz and clicks "Questions" to view all questions
3. **Find Questions**: Locates all description-type questions (li.qtype_description)
4. **Edit Questions**: For each description question:
   - Opens the question editor
   - Finds all video links (mod/url/view.php URLs)
   - For each video link:
     - Opens the SharePoint/Stream video page
     - Extracts the video thumbnail
     - Saves thumbnail locally
     - Replaces the text link with the thumbnail image
     - Makes the thumbnail clickable (links to video)
   - Saves the question changes

## Troubleshooting

### Video Playback Issues (SharePoint/Stream)
**Problem**: Videos show error page or won't play in Chromium browser
**Solution**: 
- Install and use Chrome: `playwright install chrome`
- Or use Edge: `playwright install msedge`
- The script will automatically try Chrome first, then Edge, then fall back to Chromium
- SharePoint/Stream videos require proprietary codecs that Chromium lacks

### Login Issues
- Verify your credentials are correct
- Check if your Moodle uses SSO (may need script modifications)
- Try running without `--headless` to see what's happening

### Video Thumbnail Not Found
- Ensure you have access to the SharePoint videos
- The script may need adjustments for different SharePoint/Stream layouts
- Check browser console for errors (run without --headless)

### Editor Issues
- Make sure TinyMCE is the editor (Moodle default)
- Different Moodle versions may have different HTML structures

### Timeouts
- Increase timeout values in the script if you have slow network
- Some operations have built-in delays (time.sleep) that can be adjusted

## Notes

- Thumbnails are temporarily saved to `/tmp/moodle_thumbnails/`
- The script runs with a visible browser by default to help with debugging
- Press Enter after completion to close the browser (when not in headless mode)
- Large quizzes may take significant time to process

## Customization

You can modify these aspects in the code:

- **Timeouts**: Adjust `timeout` parameters in `wait_for_selector` calls
- **Delays**: Modify `time.sleep()` values if pages load slowly
- **Temp Directory**: Change `temp_dir` path in `main()`
- **Browser**: Switch from `chromium` to `firefox` or `webkit`

## Limitations

- Only processes description-type questions
- Assumes TinyMCE editor
- Requires direct access to SharePoint videos
- Must have edit permissions for the quiz

## License

MIT License - feel free to modify and use as needed.
