"""
config/constants.py — Global constants, presets, and default configuration
=============================================================================
Centralizes all presets, resolutions, visual styles, article formats, and
default system parameters used across the entire application.
"""

from pathlib import Path
import re

# File Paths & Directories
DEFAULT_CONFIG_PATH = Path("pipeline_config.json")
DEFAULT_OUTPUT_DIR = Path("pipeline_output")
DEFAULT_SKILLS_DIR = Path("Skills")
DEFAULT_CSV_PATH = Path("Links.csv")
DEFAULT_BUNDLE_PATH = Path("offline_bundle.json")
DEFAULT_FIREBASE_CONFIG = Path("firebase_config.json")
DEFAULT_FIREBASE_SESSION = Path("firebase_session.json")

# Image Formats
IMAGE_FORMATS = {
    "webp": ("WEBP", "webp"),
    "jpeg": ("JPEG", "jpg"),
}

# Image Resolution Presets
# Width per preset; section height derives from 16:9, feature height from ~1.91:1 Open Graph ratio.
RESOLUTION_PRESETS = {
    "sd": 854,
    "hd": 1200,
    "fhd": 1920,
    "2k": 2560,
}

CUSTOM_RES_REGEX = re.compile(r"^(\d{2,5})\s*[xX]\s*(\d{2,5})$")

# Article Format Configurations
ARTICLE_FORMAT_LABELS = {
    "Standard Paragraphs (Narrative)": "paragraphs",
    "Point-Wise / Bullet Points (Scannable)": "point_wise",
    "Sub-Heading Wise (H2 + H3 Subsections)": "subheadings",
    "Hybrid (Paragraphs + Bullet Points)": "hybrid",
}
ARTICLE_FORMAT_LABELS_REV = {v: k for k, v in ARTICLE_FORMAT_LABELS.items()}

ARTICLE_FORMAT_DESCRIPTIONS = {
    "paragraphs": "Classic in-depth narrative format with 2–4 comprehensive paragraphs per section.",
    "point_wise": "Concise section intro followed by 4–6 scannable bullet points and actionable takeaways.",
    "subheadings": "Main H2 sections structured into 2–3 H3 sub-headings with focused explanations.",
    "hybrid": "Rich explanatory paragraphs followed by an actionable key takeaways / bullet list.",
}

# Visual Style Presets & Negative Prompts
IMAGE_TYPES = {
    "photo": {
        "label": "Photorealistic (35mm Documentary)",
        "prompt": "hyper-realistic documentary photography, 35mm lens, natural daylight, authentic textures, unedited raw photo, 8k resolution, cinematic lighting, sharp focus",
        "negative": "cartoon, illustration, 3d render, CGI, drawing, painting, blurry, deformed",
    },
    "cinematic": {
        "label": "Cinematic Film Still (70mm)",
        "prompt": "cinematic movie still, 70mm anamorphic lens, dramatic chiaroscuro lighting, Panavision, atmospheric haze, color graded, ultra-detailed, depth of field",
        "negative": "low quality, snapshot, amateur, flat lighting, oversaturated",
    },
    "vector": {
        "label": "Modern Flat Vector / Illustration",
        "prompt": "modern editorial flat vector illustration, clean geometric lines, minimalist aesthetic, sophisticated vibrant color palette, Behance trending graphic design",
        "negative": "photo, photorealistic, 3d, realistic textures, grainy, noisy",
    },
    "3d_render": {
        "label": "3D Isometric / Clay Render",
        "prompt": "detailed 3D isometric render, Octane Render, soft ambient occlusion, matte clay textures, clean studio lighting, smooth finishes, 4k",
        "negative": "flat 2d, sketch, photograph, grainy, distorted",
    },
    "vintage": {
        "label": "Vintage / Retro 1970s Film",
        "prompt": "vintage 1970s Kodachrome film photography, warm color tones, subtle film grain, nostalgic light leaks, timeless editorial aesthetic, retro palette",
        "negative": "modern digital look, sharp CGI, neon, plastic",
    },
    "studio": {
        "label": "Commercial Studio / Product Macro",
        "prompt": "commercial studio photography, clean white and soft neutral lighting, high-key illumination, crisp focus, hyper-detailed macro view, pristine product shot",
        "negative": "outdoor, noisy, messy background, low resolution, blurry",
    },
    "watercolor": {
        "label": "Watercolor & Ink Illustration",
        "prompt": "expressive watercolor and ink illustration, delicate pigment washes, visible paper texture, fluid artistic brushstrokes, vibrant tones, handcrafted art",
        "negative": "photo, photorealistic, 3d render, plastic, digital CGI",
    },
    "custom": {
        "label": "Custom Style",
        "prompt": "",
        "negative": "blurry, low quality, deformed, bad anatomy",
    },
}

# Pinterest Pin Style Presets
PIN_STYLE_PRESETS = {
    "inherit": "Inherit Global Visual Style",
    "photo": "Photorealistic Portrait",
    "vector": "Infographic / Vector Graphic",
    "3d_render": "3D Isometric Scene",
    "vintage": "Vintage Editorial",
    "studio": "Product Flat-Lay",
    "watercolor": "Artistic Watercolor",
    "custom": "Custom Style Descriptor",
}

# Default Application Configuration Dictionary
DEFAULT_CONFIG = {
    # System & Directories
    "output_dir": "pipeline_output",
    "db_path": "pipeline_state.db",
    "skills_dir": "Skills",
    "skills_enabled": [],
    "chars_per_section": 2000,
    "batch_size": 3,
    
    # Engine & Execution Mode
    "mode": "offline",                       # "online" (Firestore) | "offline" (Bundle/CSV)
    "offline_bundle_path": "offline_bundle.json",
    "csv_pending_stale_hours": 3,
    "quota_wait_hours": 6,
    
    # Article Transformation & Directives
    "article_format": "paragraphs",
    "master_text_prompt": "",
    
    # AI Image Generation Settings
    "image_engine": "agy_fallback",          # "agy_fallback" | "pollinations" | "agy_only" | "my_server"
    "server_url": "",                        # Colab / ngrok GPU server (/generate)
    "pollinations_delay": 180,               # seconds between calls
    "img_inter_delay": 8,                    # seconds between successful image calls
    "img_min_file_bytes": 5000,
    "img_min_stddev": 4,
    "img_max_retries": 3,
    "img_retry_delay": 15,
    "agy_timeout": 180,
    "agy_img_timeout": 120,
    "agy_idle_timeout": 150,
    "agy_empty_retries": 2,
    
    # Image Output Formats & Resolutions
    "image_format": "webp",
    "image_quality": 88,
    "image_resolution": "hd",
    "feature_resolution": "hd",
    "pin_resolution": "1000x1500",
    "heading_text_overlay": False,
    "feature_text_overlay": False,
    
    # Master Image Prompts & Styles
    "master_image_prompt": "",
    "apply_master_to_all_images": True,
    "image_type": "photo",
    "image_type_custom": "",
    "feature_image_master_prompt": "",
    "heading_image_master_prompt": "",
    
    # Pinterest Pin Settings
    "pinterest_pin": False,
    "pin_image_master_prompt": "",
    "pin_image_type": "inherit",
    "pin_image_type_custom": "",
    
    # WordPress Integration Settings
    "base_url": "",
    "username": "",
    "app_password": "",
    "status": "publish",
    "auto_publish": True,
    "seo_plugin": "rankmath",
    "alt_from": "heading",
    "verify_ssl": True,
    "max_tags": 12,
    "focus_keywords_max": 5,
    
    # Display CTA Links
    "display_links": [
        {"title": "", "url": ""},
        {"title": "", "url": ""},
        {"title": "", "url": ""},
    ],
    
    # Appearance & UI Preferences
    "theme": "dark",                         # "dark" | "light" | "system"
    "acrylic_blur": True,
    "sound_effects": False,
}
