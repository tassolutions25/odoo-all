import { patch } from "@web/core/utils/patch";
import Fullscreen from "@website_slides/js/slides_course_fullscreen_player";

// Save references to the original methods BEFORE patching
const _originalPreprocessSlideData = Fullscreen.prototype._preprocessSlideData;
const _originalRenderSlide = Fullscreen.prototype._renderSlide;

patch(Fullscreen.prototype, {
    _preprocessSlideData(slidesDataList) {
        // Call the original method without using _super
        const result = _originalPreprocessSlideData.call(this, slidesDataList);
        if (result && result.forEach) {
            result.forEach(function (slideData) {
                if (slideData.category === 'video' && slideData.videoSourceType === 'local_file') {
                    // Mark as auto-completed (no YouTube/Vimeo integration for local files)
                    slideData._autoSetDone = !slideData.hasQuestion;
                    // Restore embedCode to the raw HTML (the base method may have mangled it)
                    // The embedCode here is already set from data-embed-code HTML attribute
                }
            });
        }
        return result;
    },

    /**
     * Override _renderSlide to inject the <video> HTML for local file videos.
     */
    async _renderSlide() {
        const slide = this._slideValue;

        if (slide.category === 'video' && slide.videoSourceType === 'local_file') {
            if (this._renderSlideRunning) { return; }
            this._renderSlideRunning = true;
            try {
                const $content = this.$('.o_wslides_fs_content');
                $content.empty();
                $content.css({
                    'background': '#000',
                    'display': 'flex',
                    'align-items': 'center',
                    'justify-content': 'center',
                });

                if (slide.embedCode) {
                    // embedCode is raw <video> HTML — inject directly
                    $content.html(slide.embedCode);
                    $content.find('video').css({ 'max-width': '100%', 'max-height': '100%' });
                } else {
                    $content.html('<p style="color:white;padding:2rem;">No video found. Please re-save the slide record.</p>');
                }
            } finally {
                this._renderSlideRunning = false;
            }
            return;
        }

        // Fallback to the original _renderSlide for all other slide types
        return await _originalRenderSlide.call(this, ...arguments);
    },
});
