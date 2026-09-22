import streamlit as st
import tempfile
import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip
from moviepy.video.fx.all import resize
import cv2

# ===== FIX for Pillow 10+ =====
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Image → Video Generator Pro",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ====================== HELPER FUNCTIONS ======================
def enhance_image(image: Image.Image, sharpness=1.5, contrast=1.2, brightness=1.1, color=1.1) -> Image.Image:
    img = image.convert("RGB")
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Color(img).enhance(color)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


def add_watermark(image: Image.Image, watermark_img=None, text=None, 
                  position="bottom-right", opacity=0.4, scale=0.2) -> Image.Image:
    base = image.convert("RGBA")
    width, height = base.size
    watermark = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    if watermark_img:
        wm = watermark_img.convert("RGBA")
        wm_width = int(width * scale)
        wm_height = int(wm_width * wm.size[1] / wm.size[0])
        wm = wm.resize((wm_width, wm_height), Image.Resampling.LANCZOS)
        alpha = wm.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        wm.putalpha(alpha)

        positions = {
            "top-left": (20, 20),
            "top-right": (width - wm_width - 20, 20),
            "bottom-left": (20, height - wm_height - 20),
            "center": ((width - wm_width)//2, (height - wm_height)//2),
            "bottom-right": (width - wm_width - 20, height - wm_height - 20)
        }
        pos = positions.get(position, positions["bottom-right"])
        watermark.paste(wm, pos, wm)

    elif text:
        try:
            font = ImageFont.truetype("arial.ttf", size=int(height * 0.05))
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        positions = {
            "top-left": (20, 20),
            "top-right": (width - text_width - 20, 20),
            "bottom-left": (20, height - text_height - 20),
            "center": ((width - text_width)//2, (height - text_height)//2),
            "bottom-right": (width - text_width - 20, height - text_height - 20)
        }
        pos = positions.get(position, positions["bottom-right"])
        draw.text(pos, text, font=font, fill=(255, 255, 255, int(255 * opacity)))

    result = Image.alpha_composite(base, watermark)
    return result.convert("RGB")


def create_video_from_image(
    image: Image.Image,
    duration: float = 6.0,
    zoom_factor: float = 1.35,
    fps: int = 24,
    pan_x: float = 0.3,
    pan_y: float = 0.2,
    zoom_in: bool = True,
    title: str = None,
    title_position: str = "top",
    audio_path: str = None
) -> str:
    """Create Ken Burns style video with optional title and background music"""
    img_array = np.array(image.convert("RGB"))
    
    clip = ImageClip(img_array).set_duration(duration)
    w, h = clip.size

    def make_frame(t):
        progress = min(t / duration, 1.0)

        if zoom_in:
            current_zoom = 1.0 + (zoom_factor - 1.0) * progress
        else:
            current_zoom = zoom_factor - (zoom_factor - 1.0) * progress

        new_w = int(w * current_zoom)
        new_h = int(h * current_zoom)

        x_offset = int((new_w - w) * (0.5 + pan_x * 0.5) * progress)
        y_offset = int((new_h - h) * (0.5 + pan_y * 0.5) * progress)

        x_offset = max(0, min(x_offset, new_w - w))
        y_offset = max(0, min(y_offset, new_h - h))

        resized = resize(clip, newsize=(new_w, new_h))
        frame = resized.get_frame(t)
        return frame[y_offset:y_offset + h, x_offset:x_offset + w]

    animated = clip.fl(lambda gf, t: make_frame(t))

    # Add Title
    if title and title.strip():
        try:
            txt_clip = TextClip(
                title,
                fontsize=int(h * 0.07),
                color="white",
                font="Arial-Bold",
                stroke_color="black",
                stroke_width=2
            ).set_duration(duration)

            if title_position == "top":
                txt_clip = txt_clip.set_position(("center", 40))
            elif title_position == "center":
                txt_clip = txt_clip.set_position("center")
            else:  # bottom
                txt_clip = txt_clip.set_position(("center", h - 100))

            animated = CompositeVideoClip([animated, txt_clip])
        except Exception as e:
            st.warning(f"Could not add title: {e}")

    # Add Background Music
    if audio_path and os.path.exists(audio_path):
        try:
            audio = AudioFileClip(audio_path)
            # Loop or trim audio to match video duration
            if audio.duration < duration:
                audio = audio.fx(lambda c: c.loop(duration=duration))
            else:
                audio = audio.subclip(0, duration)
            
            # Lower volume a bit
            audio = audio.volumex(0.6)
            animated = animated.set_audio(audio)
        except Exception as e:
            st.warning(f"Could not add music: {e}")

    # Export
    fd, output_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)

    animated.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=2,
        logger=None
    )

    return output_path


# ====================== SESSION STATE ======================
if "video_path" not in st.session_state:
    st.session_state.video_path = None
if "processed_image" not in st.session_state:
    st.session_state.processed_image = None


# ====================== UI ======================
st.title("🖼️ → 🎬 Image to Video Generator Pro")
st.markdown("Enhance • Watermark • Music • Title • Cinematic Video")

st.markdown("---")

# ---------- UPLOAD IMAGE ----------
uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file:
    original_image = Image.open(uploaded_file).convert("RGB")
    st.image(original_image, caption="Original Image", use_container_width=True)

    st.markdown("---")
    st.subheader("🛠️ Image Tools")

    # Enhance
    with st.expander("✨ Enhance Image Quality", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1: sharpness = st.slider("Sharpness", 0.5, 3.0, 1.5, 0.1)
        with c2: contrast = st.slider("Contrast", 0.5, 2.0, 1.2, 0.1)
        with c3: brightness = st.slider("Brightness", 0.5, 2.0, 1.1, 0.1)
        with c4: color = st.slider("Color", 0.5, 2.0, 1.1, 0.1)

        if st.button("Apply Enhancement"):
            enhanced = enhance_image(original_image, sharpness, contrast, brightness, color)
            st.session_state.processed_image = enhanced
            st.success("Enhanced!")
            st.image(enhanced, use_container_width=True)

    # Add Watermark
    with st.expander("💧 Add Watermark"):
        wm_type = st.radio("Type", ["Text", "Logo"], horizontal=True)
        position = st.selectbox("Position", ["bottom-right", "bottom-left", "top-right", "top-left", "center"])
        opacity = st.slider("Opacity", 0.1, 1.0, 0.45, 0.05)

        if wm_type == "Text":
            wm_text = st.text_input("Watermark Text", "© My Brand")
            if st.button("Add Text Watermark"):
                base = st.session_state.processed_image or original_image
                result = add_watermark(base, text=wm_text, position=position, opacity=opacity)
                st.session_state.processed_image = result
                st.image(result, use_container_width=True)
        else:
            wm_file = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"], key="logo")
            scale = st.slider("Logo Size", 0.05, 0.35, 0.15)
            if wm_file and st.button("Add Logo Watermark"):
                wm_img = Image.open(wm_file)
                base = st.session_state.processed_image or original_image
                result = add_watermark(base, watermark_img=wm_img, position=position, opacity=opacity, scale=scale)
                st.session_state.processed_image = result
                st.image(result, use_container_width=True)

    if st.session_state.processed_image:
        st.markdown("**Current Processed Image:**")
        st.image(st.session_state.processed_image, use_container_width=True)
        if st.button("Reset Image"):
            st.session_state.processed_image = None
            st.rerun()

    # ====================== VIDEO SETTINGS ======================
    st.markdown("---")
    st.subheader("🎬 Video Settings")

    col1, col2 = st.columns(2)
    with col1:
        duration = st.slider("Duration (seconds)", 3.0, 15.0, 6.0, 0.5)
        zoom = st.slider("Zoom Intensity", 1.1, 2.0, 1.35, 0.05)
    with col2:
        motion = st.selectbox("Motion Style", [
            "Zoom In (Center)",
            "Zoom Out",
            "Pan Left to Right",
            "Pan Right to Left",
            "Pan Up",
            "Pan Down"
        ])

    # ---------- TITLE ----------
    st.markdown("##### 📝 Title / Text Overlay")
    title_text = st.text_input("Video Title", placeholder="My Beautiful Memory")
    title_position = st.selectbox("Title Position", ["top", "center", "bottom"], index=0)

    # ---------- BACKGROUND MUSIC ----------
    st.markdown("##### 🎵 Background Music")
    audio_file = st.file_uploader("Upload MP3 / WAV music", type=["mp3", "wav", "m4a"])

    # Generate Button
    if st.button("🎬 Generate Video", type="primary", use_container_width=True):
        final_image = st.session_state.processed_image or original_image

        # Motion parameters
        zoom_in = True
        pan_x, pan_y = 0.0, 0.0
        if motion == "Zoom Out":
            zoom_in = False
        elif motion == "Pan Left to Right":
            pan_x = 0.6
        elif motion == "Pan Right to Left":
            pan_x = -0.6
        elif motion == "Pan Up":
            pan_y = -0.5
        elif motion == "Pan Down":
            pan_y = 0.5

        # Save audio temporarily
        audio_path = None
        if audio_file:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tfile.write(audio_file.read())
            audio_path = tfile.name
            tfile.close()

        with st.spinner("Generating video with music and title... Please wait"):
            try:
                if st.session_state.video_path and os.path.exists(st.session_state.video_path):
                    try:
                        os.unlink(st.session_state.video_path)
                    except:
                        pass

                video_path = create_video_from_image(
                    final_image,
                    duration=duration,
                    zoom_factor=zoom,
                    pan_x=pan_x,
                    pan_y=pan_y,
                    zoom_in=zoom_in,
                    title=title_text,
                    title_position=title_position,
                    audio_path=audio_path
                )
                st.session_state.video_path = video_path
                st.success("✅ Video generated successfully!")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                # Clean temp audio
                if audio_path and os.path.exists(audio_path):
                    try:
                        os.unlink(audio_path)
                    except:
                        pass

# ---------- RESULT ----------
if st.session_state.video_path and os.path.exists(st.session_state.video_path):
    st.markdown("---")
    st.subheader("📥 Your Video is Ready")
    st.video(st.session_state.video_path)

    with open(st.session_state.video_path, "rb") as f:
        video_bytes = f.read()

    st.download_button(
        label="⬇️ Download Video (MP4)",
        data=video_bytes,
        file_name="my_video.mp4",
        mime="video/mp4",
        use_container_width=True
    )
