import streamlit as st
import tempfile
import os
from PIL import Image
import numpy as np
from moviepy.editor import ImageClip
from moviepy.video.fx.all import resize

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Image → Video Generator",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ====================== HELPER FUNCTION ======================
def create_video_from_image(
    image: Image.Image,
    duration: float = 6.0,
    zoom_factor: float = 1.35,
    fps: int = 24
) -> str:
    """Create a Ken Burns style video from a single image."""
    img_array = np.array(image.convert("RGB"))
    
    clip = ImageClip(img_array).set_duration(duration)
    w, h = clip.size

    def make_frame(t):
        progress = min(t / duration, 1.0)
        current_zoom = 1.0 + (zoom_factor - 1.0) * progress

        new_w = int(w * current_zoom)
        new_h = int(h * current_zoom)

        # Slight pan while zooming
        x_offset = int((new_w - w) * 0.35 * progress)
        y_offset = int((new_h - h) * 0.25 * progress)

        # Resize then crop
        resized = resize(clip, newsize=(new_w, new_h))
        frame = resized.get_frame(t)
        
        return frame[y_offset:y_offset + h, x_offset:x_offset + w]

    animated = clip.fl(lambda gf, t: make_frame(t))

    # Create temporary file
    fd, output_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)

    animated.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio=False,
        preset="ultrafast",
        threads=2,
        logger=None
    )

    return output_path


# ====================== SESSION STATE ======================
if "video_path" not in st.session_state:
    st.session_state.video_path = None


# ====================== UI ======================
st.title("🖼️ → 🎬 Image to Video Generator")
st.markdown("Upload a photo → get a cinematic Ken Burns style video.")

st.markdown("---")

# ---------- UPLOAD + GENERATE ----------
uploaded_file = st.file_uploader(
    "Choose an image",
    type=["jpg", "jpeg", "png", "webp"],
    help="Best results with high-resolution landscape photos"
)

col_a, col_b = st.columns(2)
with col_a:
    duration = st.slider("Video duration (seconds)", 3.0, 12.0, 6.0, 0.5)
with col_b:
    zoom = st.slider("Zoom intensity", 1.1, 2.0, 1.35, 0.05)

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Preview", use_container_width=True)

    if st.button("🎬 Generate Video", type="primary", use_container_width=True):
        with st.spinner("Generating your video... this may take 10–30 seconds"):
            try:
                # Clean previous video if exists
                if st.session_state.video_path and os.path.exists(st.session_state.video_path):
                    try:
                        os.unlink(st.session_state.video_path)
                    except Exception:
                        pass

                video_path = create_video_from_image(
                    image,
                    duration=duration,
                    zoom_factor=zoom
                )
                st.session_state.video_path = video_path
                st.success("Video generated successfully!")
            except Exception as e:
                st.error(f"Error generating video: {e}")

# ---------- DOWNLOAD ----------
if st.session_state.video_path and os.path.exists(st.session_state.video_path):
    st.markdown("---")
    st.subheader("📥 Your Video is Ready")

    st.video(st.session_state.video_path)

    with open(st.session_state.video_path, "rb") as f:
        video_bytes = f.read()

    st.download_button(
        label="⬇️ Download Video (MP4)",
        data=video_bytes,
        file_name="generated_video.mp4",
        mime="video/mp4",
        use_container_width=True
    )
