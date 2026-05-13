"""Curated Edge TTS voice catalog grouped by language.

The Edge TTS service exposes hundreds of `*-Neural` voices; the picker only
needs the most common ones. We ship a hand-picked subset (~25 languages,
2-4 voices each) so the dropdown stays navigable and works offline. Power
users can still set arbitrary voice IDs via `RESPEAKER_BASE_VOICE` in `.env`
— anything passed through that path is honored as-is.

The base voice controls the *language*, accent, and gender baseline that
Edge TTS produces before RVC voice conversion kicks in. Switching from
`en-US-JennyNeural` to `es-ES-ElviraNeural` makes the synthesizer speak
Spanish; the RVC step then re-colors that Spanish audio in the target
voice.
"""

from __future__ import annotations

from typing import Iterable

DEFAULT_VOICE = "en-US-JennyNeural"


VOICES_BY_LANGUAGE: dict[str, list[tuple[str, str]]] = {
    "English (US)": [
        ("en-US-JennyNeural", "Jenny — Female"),
        ("en-US-AriaNeural", "Aria — Female"),
        ("en-US-MichelleNeural", "Michelle — Female"),
        ("en-US-GuyNeural", "Guy — Male"),
        ("en-US-ChristopherNeural", "Christopher — Male"),
        ("en-US-EricNeural", "Eric — Male"),
    ],
    "English (UK)": [
        ("en-GB-SoniaNeural", "Sonia — Female"),
        ("en-GB-LibbyNeural", "Libby — Female"),
        ("en-GB-RyanNeural", "Ryan — Male"),
    ],
    "English (Australia)": [
        ("en-AU-NatashaNeural", "Natasha — Female"),
        ("en-AU-WilliamNeural", "William — Male"),
    ],
    "English (India)": [
        ("en-IN-NeerjaNeural", "Neerja — Female"),
        ("en-IN-PrabhatNeural", "Prabhat — Male"),
    ],
    "Spanish (Spain)": [
        ("es-ES-ElviraNeural", "Elvira — Female"),
        ("es-ES-AlvaroNeural", "Alvaro — Male"),
    ],
    "Spanish (Mexico)": [
        ("es-MX-DaliaNeural", "Dalia — Female"),
        ("es-MX-JorgeNeural", "Jorge — Male"),
    ],
    "French (France)": [
        ("fr-FR-DeniseNeural", "Denise — Female"),
        ("fr-FR-EloiseNeural", "Eloise — Female"),
        ("fr-FR-HenriNeural", "Henri — Male"),
    ],
    "French (Canada)": [
        ("fr-CA-SylvieNeural", "Sylvie — Female"),
        ("fr-CA-AntoineNeural", "Antoine — Male"),
    ],
    "German": [
        ("de-DE-KatjaNeural", "Katja — Female"),
        ("de-DE-AmalaNeural", "Amala — Female"),
        ("de-DE-ConradNeural", "Conrad — Male"),
    ],
    "Italian": [
        ("it-IT-ElsaNeural", "Elsa — Female"),
        ("it-IT-IsabellaNeural", "Isabella — Female"),
        ("it-IT-DiegoNeural", "Diego — Male"),
    ],
    "Portuguese (Brazil)": [
        ("pt-BR-FranciscaNeural", "Francisca — Female"),
        ("pt-BR-AntonioNeural", "Antonio — Male"),
    ],
    "Portuguese (Portugal)": [
        ("pt-PT-RaquelNeural", "Raquel — Female"),
        ("pt-PT-DuarteNeural", "Duarte — Male"),
    ],
    "Dutch": [
        ("nl-NL-ColetteNeural", "Colette — Female"),
        ("nl-NL-MaartenNeural", "Maarten — Male"),
    ],
    "Polish": [
        ("pl-PL-ZofiaNeural", "Zofia — Female"),
        ("pl-PL-MarekNeural", "Marek — Male"),
    ],
    "Russian": [
        ("ru-RU-SvetlanaNeural", "Svetlana — Female"),
        ("ru-RU-DmitryNeural", "Dmitry — Male"),
    ],
    "Turkish": [
        ("tr-TR-EmelNeural", "Emel — Female"),
        ("tr-TR-AhmetNeural", "Ahmet — Male"),
    ],
    "Swedish": [
        ("sv-SE-SofieNeural", "Sofie — Female"),
        ("sv-SE-MattiasNeural", "Mattias — Male"),
    ],
    "Arabic (Egypt)": [
        ("ar-EG-SalmaNeural", "Salma — Female"),
        ("ar-EG-ShakirNeural", "Shakir — Male"),
    ],
    "Hindi": [
        ("hi-IN-SwaraNeural", "Swara — Female"),
        ("hi-IN-MadhurNeural", "Madhur — Male"),
    ],
    "Japanese": [
        ("ja-JP-NanamiNeural", "Nanami — Female"),
        ("ja-JP-KeitaNeural", "Keita — Male"),
    ],
    "Korean": [
        ("ko-KR-SunHiNeural", "SunHi — Female"),
        ("ko-KR-InJoonNeural", "InJoon — Male"),
    ],
    "Chinese (Mandarin)": [
        ("zh-CN-XiaoxiaoNeural", "Xiaoxiao — Female"),
        ("zh-CN-XiaoyiNeural", "Xiaoyi — Female"),
        ("zh-CN-YunxiNeural", "Yunxi — Male"),
        ("zh-CN-YunyangNeural", "Yunyang — Male"),
    ],
    "Chinese (Cantonese)": [
        ("zh-HK-HiuMaanNeural", "HiuMaan — Female"),
        ("zh-HK-WanLungNeural", "WanLung — Male"),
    ],
    "Indonesian": [
        ("id-ID-GadisNeural", "Gadis — Female"),
        ("id-ID-ArdiNeural", "Ardi — Male"),
    ],
    "Malay": [
        ("ms-MY-YasminNeural", "Yasmin — Female"),
        ("ms-MY-OsmanNeural", "Osman — Male"),
    ],
    "Vietnamese": [
        ("vi-VN-HoaiMyNeural", "HoaiMy — Female"),
        ("vi-VN-NamMinhNeural", "NamMinh — Male"),
    ],
    "Thai": [
        ("th-TH-PremwadeeNeural", "Premwadee — Female"),
        ("th-TH-NiwatNeural", "Niwat — Male"),
    ],
}


def languages() -> list[str]:
    """Ordered list of language group names — use to populate the language combo."""
    return list(VOICES_BY_LANGUAGE.keys())


def voices_for_language(language: str) -> list[tuple[str, str]]:
    """Return [(voice_id, display_label), ...] for the given language group."""
    return list(VOICES_BY_LANGUAGE.get(language, []))


def all_voices() -> Iterable[tuple[str, str, str]]:
    """Iterate (language, voice_id, display_label) across the whole catalog."""
    for lang, entries in VOICES_BY_LANGUAGE.items():
        for voice_id, label in entries:
            yield lang, voice_id, label


def find_language(voice_id: str) -> str | None:
    """Return the language group name for a voice id, or None if unknown."""
    if not voice_id:
        return None
    for lang, entries in VOICES_BY_LANGUAGE.items():
        for vid, _ in entries:
            if vid == voice_id:
                return lang
    return None


def display_label(voice_id: str) -> str:
    """Human label for a voice id; falls back to the id itself if uncurated."""
    for _lang, entries in VOICES_BY_LANGUAGE.items():
        for vid, label in entries:
            if vid == voice_id:
                return label
    return voice_id
