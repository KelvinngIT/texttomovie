import streamlit as st
import tempfile
import os
import re
from PIL import Image
import numpy as np
from moviepy.editor import ImageClip
from moviepy.video.fx.all import resize

# ===== FIX for Pillow 10+ =====
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Image → Video Generator",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ====================== HELPER FUNCTIONS ======================
def parse_motion_prompt(prompt: str) -> dict:
    """
    Simple keyword-based parser for motion description.
    Returns parameters: zoom_direction, pan_x, pan_y, zoom_intensity
    """
    prompt = prompt.lower().strip()

    # Default values
    params = {
        "zoom_in": True,          # True = zoom in, False = zoom out
        "pan_x": 0.0,             # -1 (left) to +1 (right)
        "pan_y": 0.0,             # -1 (up) to +1 (down)
        "zoom_intensity": 1.35,
    }

    # Zoom direction
    if any(word in prompt for word in ["zoom out", "pull out", "pull back", "reveal"]):
        params["zoom_in"] = False
    elif any(word in prompt for word in ["zoom in", "push in", "close up", "closer"]):
        params["zoom_in"] = True

    # Horizontal pan
    if any(word in prompt for word in ["left", "to the left", "from right"]):
        params["pan_x"] = -0.6
    elif any(word in prompt for word in ["right", "to the right", "from left"]):
        params["pan_x"] = 0.6

    # Vertical pan
    if any(word in prompt for word in ["up", "top", "upward"]):
        params["pan_y"] = -0.5
    elif any(word in prompt for word in ["down", "bottom", "downward"]):
        params["pan_y"] = 0.5

    # Intensity
    if any(word in prompt for word in ["strong", "dramatic", "heavy", "big"]):
        params["zoom_intensity"] = 1.6
    elif any(word in prompt for word in ["gentle", "subtle", "soft", "slow"]):
        params["zoom_intensity"] = 1.2

    # Center focus
    if "center" in prompt or "middle" in prompt:
        params["pan_x"] = 0.0
        params["pan_y"] = 0.0

    return params


def create_video_from_image(
    image: Image.Image,
    duration: float = 6.0,
    zoom_factor: float = 1.35,
    fps: int = 24,
    pan_x: float = 0.3,
    pan_y: float = 0.2,
    zoom_in: bool = True
) -> str:
    """Create a Ken Burns style video from a single image with controllable motion."""
    img_array = np.array(image.convert("RGB"))
    
    clip = ImageClip(img_array).set_duration(duration)
    w, h = clip.size

    def make_frame(t):
        progress = min(t / duration, 1.0)

        if zoom_in:
            current_zoom = 1.0 + (zoom_factor - 1.0) * progress
        else:
            # Zoom out
            current_zoom = zoom_factor - (zoom_factor - 1.0) * progress

        new_w = int(w * current_zoom)
        new_h = int(h * current_zoom)

        # Pan direction controlled by pan_x / pan_y (-1 to 1)
        x_offset = int((new_w - w) * (0.5 + pan_x * 0.5) * progress)
        y_offset = int((new_h - h) * (0.5 + pan_y * 0.5) * progress)

        # Keep offsets inside bounds
        x_offset = max(0, min(x_offset, new_w - w))
        y_offset = max(0, min(y_offset, new_h - h))

        resized = resize(clip, newsize=(new_w, new_h))
        frame = resized.get_frame(t)
        
        return frame[y_offset:y_offset + h, x_offset:x_offset + w]

    animated = clip.fl(lambda gf, t: make_frame(t))

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
st.markdown("Upload a photo and describe the camera movement you want.")

st.markdown("---")

# ---------- UPLOAD ----------
uploaded_file = st.file_uploader(
    "Choose an image",
    type=["jpg", "jpeg", "png", "webp"],
    help="Best results with high-resolution photos"
)

# ---------- TEXT PROMPT ----------
st.subheader("✍️ Describe the video movement")
motion_prompt = st.text_area(
    "What kind of camera movement do you want?",
    placeholder="Examples:\n• slow zoom in to the center\n• pan from left to right\n• zoom out from the top\n• dramatic push in\n• gentle drift right",
    height=100
)

# ---------- SETTINGS ----------
col_a, col_b = st.columns(2)
with col_a:
    duration = st.slider("Video duration (seconds)", 3.0, 12.0, 6.0, 0.5)
with col_b:
    # Manual override still available
    manual_zoom = st.slider("Zoom intensity (manual override)", 1.1, 2.0, 1.35, 0.05)

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Preview", use_container_width=True)

    if st.button("🎬 Generate Video", type="primary", use_container_width=True):
        with st.spinner("Generating your video... this may take 10–30 seconds"):
            try:
                # Parse the text prompt
                motion = parse_motion_prompt(motion_prompt)

                # Use prompt intensity if user wrote something, otherwise use slider
                final_zoom = motion["zoom_intensity"] if motion_prompt.strip() else manual_zoom

                # Clean previous video
                if st.session_state.video_path and os.path.exists(st.session_state.video_path):
                    try:
                        os.unlink(st.session_state.video_path)
                    except Exception:
                        pass

                video_path = create_video_from_image(
                    image,
                    duration=duration,
                    zoom_factor=final_zoom,
                    pan_x=motion["pan_x"],
                    pan_y=motion["pan_y"],
                    zoom_in=motion["zoom_in"]
                )
                st.session_state.video_path = video_path
                st.success("Video generated successfully!")
                
                # Show what the AI understood
                with st.expander("🧠 Motion interpreted as"):
                    st.write(f"- Zoom: {'In' if motion['zoom_in'] else 'Out'}")
                    st.write(f"- Horizontal pan: {motion['pan_x']:.1f}")
                    st.write(f"- Vertical pan: {motion['pan_y']:.1f}")
                    st.write(f"- Intensity: {final_zoom:.2f}")

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
