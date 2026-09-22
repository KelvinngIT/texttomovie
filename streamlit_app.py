import streamlit as st
import tempfile
import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from moviepy.editor import ImageClip
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
    """Enhance image quality"""
    img = image.convert("RGB")
    
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(sharpness)
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)
    
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness)
    
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(color)
    
    # Mild denoise
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    return img


def remove_watermark_simple(image: Image.Image, method="crop", crop_box=None) -> Image.Image:
    """
    Simple watermark removal.
    method: "crop" or "inpaint"
    """
    img = image.convert("RGB")
    
    if method == "crop" and crop_box:
        # crop_box = (left, top, right, bottom)
        return img.crop(crop_box)
    
    elif method == "inpaint":
        # Basic OpenCV inpainting (works only for solid watermarks)
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Create a simple mask (user should ideally draw it)
        # For demo: assume watermark is in bottom-right corner
        h, w = img_cv.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[int(h*0.85):, int(w*0.7):] = 255   # bottom-right area
        
        result = cv2.inpaint(img_cv, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    
    return img


def add_watermark(image: Image.Image, watermark_img=None, text=None, 
                  position="bottom-right", opacity=0.4, scale=0.2) -> Image.Image:
    """Add logo or text watermark"""
    base = image.convert("RGBA")
    width, height = base.size
    
    # Create watermark layer
    watermark = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    
    if watermark_img:
        # Logo watermark
        wm = watermark_img.convert("RGBA")
        wm_width = int(width * scale)
        wm_height = int(wm_width * wm.size[1] / wm.size[0])
        wm = wm.resize((wm_width, wm_height), Image.Resampling.LANCZOS)
        
        # Apply opacity
        alpha = wm.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        wm.putalpha(alpha)
        
        # Position
        if position == "top-left":
            pos = (20, 20)
        elif position == "top-right":
            pos = (width - wm_width - 20, 20)
        elif position == "bottom-left":
            pos = (20, height - wm_height - 20)
        elif position == "center":
            pos = ((width - wm_width)//2, (height - wm_height)//2)
        else:  # bottom-right
            pos = (width - wm_width - 20, height - wm_height - 20)
        
        watermark.paste(wm, pos, wm)
    
    elif text:
        # Text watermark
        try:
            font = ImageFont.truetype("arial.ttf", size=int(height * 0.05))
        except:
            font = ImageFont.load_default()
        
        # Get text size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        if position == "top-left":
            pos = (20, 20)
        elif position == "top-right":
            pos = (width - text_width - 20, 20)
        elif position == "bottom-left":
            pos = (20, height - text_height - 20)
        elif position == "center":
            pos = ((width - text_width)//2, (height - text_height)//2)
        else:
            pos = (width - text_width - 20, height - text_height - 20)
        
        # Draw semi-transparent text
        draw.text(pos, text, font=font, fill=(255, 255, 255, int(255 * opacity)))
    
    # Composite
    result = Image.alpha_composite(base, watermark)
    return result.convert("RGB")


def create_video_from_image(
    image: Image.Image,
    duration: float = 6.0,
    zoom_factor: float = 1.35,
    fps: int = 24,
    pan_x: float = 0.3,
    pan_y: float = 0.2,
    zoom_in: bool = True
) -> str:
    """Create Ken Burns style video"""
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
if "processed_image" not in st.session_state:
    st.session_state.processed_image = None


# ====================== UI ======================
st.title("🖼️ → 🎬 Image to Video Generator Pro")
st.markdown("Enhance image • Remove/Add watermark • Create cinematic video")

st.markdown("---")

# ---------- UPLOAD ----------
uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file:
    original_image = Image.open(uploaded_file).convert("RGB")
    st.image(original_image, caption="Original Image", use_container_width=True)

    st.markdown("---")
    st.subheader("🛠️ Image Tools")

    # ===== 1. ENHANCE IMAGE =====
    with st.expander("✨ Enhance Image Quality", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sharpness = st.slider("Sharpness", 0.5, 3.0, 1.5, 0.1)
        with col2:
            contrast = st.slider("Contrast", 0.5, 2.0, 1.2, 0.1)
        with col3:
            brightness = st.slider("Brightness", 0.5, 2.0, 1.1, 0.1)
        with col4:
            color = st.slider("Color", 0.5, 2.0, 1.1, 0.1)

        if st.button("Apply Enhancement"):
            enhanced = enhance_image(original_image, sharpness, contrast, brightness, color)
            st.session_state.processed_image = enhanced
            st.success("Image enhanced!")
            st.image(enhanced, caption="Enhanced Image", use_container_width=True)

    # ===== 2. REMOVE WATERMARK =====
    with st.expander("🧹 Remove Watermark"):
        st.info("Simple removal works best for solid watermarks in the corner.")
        
        remove_method = st.radio("Method", ["Crop (Recommended)", "Auto Inpaint (Bottom-Right)"])
        
        if remove_method == "Crop (Recommended)":
            st.write("Enter crop values (leave some margin around the watermark):")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                left = st.number_input("Left", 0, original_image.width, 0)
            with c2:
                top = st.number_input("Top", 0, original_image.height, 0)
            with c3:
                right = st.number_input("Right", 0, original_image.width, original_image.width)
            with c4:
                bottom = st.number_input("Bottom", 0, original_image.height, original_image.height)
            
            if st.button("Apply Crop"):
                cropped = original_image.crop((left, top, right, bottom))
                st.session_state.processed_image = cropped
                st.success("Cropped successfully!")
                st.image(cropped, use_container_width=True)
        
        else:
            if st.button("Try Auto Inpaint"):
                result = remove_watermark_simple(original_image, method="inpaint")
                st.session_state.processed_image = result
                st.success("Inpainting applied (best for solid watermarks)")
                st.image(result, use_container_width=True)

    # ===== 3. ADD WATERMARK =====
    with st.expander("💧 Add Watermark"):
        wm_type = st.radio("Watermark Type", ["Text", "Logo Image"])
        
        position = st.selectbox("Position", ["bottom-right", "bottom-left", "top-right", "top-left", "center"])
        opacity = st.slider("Opacity", 0.1, 1.0, 0.4, 0.05)
        
        if wm_type == "Text":
            wm_text = st.text_input("Watermark Text", value="© My Brand")
            if st.button("Add Text Watermark"):
                base_img = st.session_state.processed_image or original_image
                result = add_watermark(base_img, text=wm_text, position=position, opacity=opacity)
                st.session_state.processed_image = result
                st.success("Text watermark added!")
                st.image(result, use_container_width=True)
        
        else:
            wm_file = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg", "webp"], key="wm")
            scale = st.slider("Logo Size", 0.05, 0.4, 0.15, 0.01)
            
            if wm_file and st.button("Add Logo Watermark"):
                wm_img = Image.open(wm_file)
                base_img = st.session_state.processed_image or original_image
                result = add_watermark(base_img, watermark_img=wm_img, position=position, opacity=opacity, scale=scale)
                st.session_state.processed_image = result
                st.success("Logo watermark added!")
                st.image(result, use_container_width=True)

    # Show current processed image
    if st.session_state.processed_image:
        st.markdown("---")
        st.subheader("Current Processed Image")
        st.image(st.session_state.processed_image, use_container_width=True)
        
        if st.button("Reset to Original"):
            st.session_state.processed_image = None
            st.rerun()

    # ===== GENERATE VIDEO =====
    st.markdown("---")
    st.subheader("🎬 Generate Video")

    col_a, col_b = st.columns(2)
    with col_a:
        duration = st.slider("Duration (seconds)", 3.0, 12.0, 6.0, 0.5)
    with col_b:
        zoom = st.slider("Zoom Intensity", 1.1, 2.0, 1.35, 0.05)

    motion = st.selectbox("Motion Style", [
        "Zoom In (Center)",
        "Zoom Out",
        "Pan Left to Right",
        "Pan Right to Left",
        "Pan Up",
        "Pan Down"
    ])

    if st.button("🎬 Generate Video", type="primary", use_container_width=True):
        final_image = st.session_state.processed_image or original_image
        
        # Set motion parameters
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

        with st.spinner("Generating video..."):
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
                    zoom_in=zoom_in
                )
                st.session_state.video_path = video_path
                st.success("Video generated successfully!")
            except Exception as e:
                st.error(f"Error: {e}")

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
