from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1350
WHITE = (245, 247, 244, 255)
PALE = (190, 225, 236, 255)
MUTED = (170, 199, 207, 255)
BLUE = (73, 190, 237, 255)
AMBER = (239, 165, 45, 255)
LINE = (212, 229, 232, 115)


def load_font(size: int, bold: bool = False, condensed: bool = False) -> ImageFont.FreeTypeFont:
    names = []
    if condensed:
        names.extend([
            r"C:\Windows\Fonts\bahnschrift.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        ])
    elif bold:
        names.extend([
            r"C:\Windows\Fonts\segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ])
    else:
        names.extend([
            r"C:\Windows\Fonts\segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ])
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default(size=size)


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill=WHITE) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, font=font, fill=fill)


def glass(base: Image.Image, box: tuple[int, int, int, int], radius: int, fill=(7, 35, 52, 210)) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=(220, 234, 229, 120), width=2)
    base.alpha_composite(layer)


def cloud_icon(base: Image.Image, center: tuple[int, int], condition: str, scale: float = 1.0) -> None:
    x, y = center
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if condition in {"clear"}:
        r = int(28 * scale)
        d.ellipse((x-r, y-r, x+r, y+r), fill=AMBER)
        for i in range(8):
            a = math.radians(i * 45)
            d.line((x + math.cos(a)*38*scale, y + math.sin(a)*38*scale,
                    x + math.cos(a)*52*scale, y + math.sin(a)*52*scale), fill=AMBER, width=max(2, int(4*scale)))
    else:
        if condition == "partly-cloudy":
            d.ellipse((x+8*scale, y-48*scale, x+58*scale, y+2*scale), fill=AMBER)
        color = (239, 244, 245, 255)
        d.ellipse((x-60*scale, y-18*scale, x+12*scale, y+42*scale), fill=color)
        d.ellipse((x-25*scale, y-52*scale, x+45*scale, y+42*scale), fill=color)
        d.ellipse((x+15*scale, y-24*scale, x+72*scale, y+42*scale), fill=color)
        d.rounded_rectangle((x-60*scale, y, x+72*scale, y+44*scale), radius=int(20*scale), fill=color)
        if "rain" in condition or condition == "drizzle":
            for dx in (-38, -8, 22, 52):
                d.line((x+dx*scale, y+55*scale, x+(dx-8)*scale, y+75*scale), fill=BLUE, width=max(2, int(4*scale)))
    base.alpha_composite(layer)


def format_temp(value) -> str:
    if value is None:
        return "—"
    value = int(round(float(value)))
    return f"{value:+d}°"


def choose_venue(venues: list[dict], target_date: str, rotation: list[str], strict: bool) -> tuple[dict, list[str]]:
    target = date.fromisoformat(target_date)
    ordinal = target.toordinal()
    wanted = rotation[ordinal % len(rotation)]

    def used_within_week(venue: dict) -> bool:
        for raw_date in venue.get("used_dates", []):
            used_date = date.fromisoformat(raw_date)
            age = (target - used_date).days
            if 0 <= age < 7:
                return True
        return False

    candidates = [
        v for v in venues
        if v.get("ready")
        and v.get("category") == wanted
        and v.get("image")
        and not used_within_week(v)
    ]
    warnings: list[str] = []
    if not candidates:
        raise ValueError(
            f"No unused publication-ready venue for rotation category: {wanted}. "
            "Add and verify a new venue instead of repeating an old one."
        )
    if strict and warnings:
        raise ValueError("; ".join(warnings))
    return candidates[ordinal % len(candidates)], warnings


def add_foreground(base: Image.Image, asset_path: Path) -> None:
    item = Image.open(asset_path).convert("RGBA")
    alpha_box = item.getchannel("A").getbbox()
    if alpha_box:
        item = item.crop(alpha_box)
    target_w = 400
    item = item.resize((target_w, round(item.height * target_w / item.width)), Image.Resampling.LANCZOS)
    x = W - item.width - 18
    # The approved composition keeps the menu item inside the lower venue zone.
    # Tall glasses intentionally continue below the canvas instead of covering
    # the main weather panel.
    y = 1000 if item.height > 420 else 1060
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_alpha = item.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda p: p * 80 // 255)
    shadow_piece = Image.new("RGBA", item.size, (0, 0, 0, 255))
    shadow_piece.putalpha(shadow_alpha)
    shadow.alpha_composite(shadow_piece, (x + 10, y + 14))
    base.alpha_composite(shadow)
    base.alpha_composite(item, (x, y))


def render(weather: dict, venue: dict, config: dict, output: Path, warnings: list[str]) -> Path:
    background = Image.open(ROOT / config["background"]).convert("RGB")
    base = ImageOps.fit(background, (W, H), method=Image.Resampling.LANCZOS).convert("RGBA")
    base = ImageEnhance.Contrast(base).enhance(1.03)
    base = Image.alpha_composite(base, Image.new("RGBA", base.size, (3, 14, 23, 28)))
    d = ImageDraw.Draw(base)

    today = weather["today"]
    tomorrow = weather["tomorrow"]
    today_dt = datetime.fromisoformat(today["date"])
    tomorrow_dt = datetime.fromisoformat(tomorrow["date"])
    months = ["", "ЯНВАРЯ", "ФЕВРАЛЯ", "МАРТА", "АПРЕЛЯ", "МАЯ", "ИЮНЯ", "ИЮЛЯ", "АВГУСТА", "СЕНТЯБРЯ", "ОКТЯБРЯ", "НОЯБРЯ", "ДЕКАБРЯ"]

    glass(base, (68, 18, 1012, 142), 28, (7, 35, 54, 142))
    d = ImageDraw.Draw(base)
    d.ellipse((145, 49, 171, 75), fill=PALE)
    d.polygon(((148, 66), (168, 66), (158, 89)), fill=PALE)
    d.ellipse((153, 56, 163, 66), fill=(40, 89, 105, 255))
    d.text((182, 36), "САНКТ-ПЕТЕРБУРГ", font=load_font(42, condensed=True), fill=WHITE)
    centered(d, (W // 2, 109), "БАРОМЕТР • ПРОГНОЗ НА ЗАВТРА", load_font(18, bold=True), AMBER)

    glass(base, (72, 158, 1008, 326), 30, (7, 35, 52, 172))
    centered(d, (W // 2, 181), f"СЕГОДНЯ • {today_dt.day} {months[today_dt.month]}", load_font(19, bold=True))
    periods = [("УТРО", today["morning"]), ("ДЕНЬ", today["day"]), ("ВЕЧЕР", today["evening"])]
    for cx, (label, period) in zip((245, 540, 835), periods):
        centered(d, (cx, 224), label, load_font(17, bold=True), PALE)
        centered(d, (cx, 256), format_temp(period.get("temp")), load_font(25, condensed=True))
        cloud_icon(base, (cx, 294), period.get("condition", "cloudy"), .42)
    d = ImageDraw.Draw(base)
    d.line((392, 202, 392, 301), fill=LINE, width=2)
    d.line((687, 202, 687, 301), fill=LINE, width=2)

    glass(base, (72, 344, 1008, 1040), 34, (7, 35, 52, 240))
    d = ImageDraw.Draw(base)
    centered(d, (W // 2, 389), f"ЗАВТРА • {tomorrow_dt.day} {months[tomorrow_dt.month]}", load_font(24, bold=True), PALE)
    centered(d, (W // 2, 520), format_temp(tomorrow["day_temp"]), load_font(116, condensed=True))
    cloud_icon(base, (W // 2, 615), tomorrow.get("condition", "cloudy"), 1.12)
    centered(d, (W // 2, 715), tomorrow["condition_text"], load_font(32, condensed=True), PALE)
    centered(d, (W // 2, 755), f"ДНЁМ ДО {format_temp(tomorrow['day_temp'])}  •  НОЧЬЮ {format_temp(tomorrow['night_temp'])}", load_font(16, bold=True), MUTED)

    timeline = tomorrow["hourly_precipitation"]
    xs = [205, 350, 495, 640, 785, 930]
    y = 812
    d.line((xs[0], y, xs[-1], y), fill=(190, 212, 221, 180), width=5)
    uses_amounts = all("amount_mm" in item for item in timeline)
    for item, x in zip(timeline, xs):
        prob = int(item.get("probability", 0))
        amount = float(item.get("amount_mm", 0))
        has_rain = bool(item.get("has_precipitation", amount >= 0.1 if uses_amounts else prob >= 20))
        centered(d, (x, y - 28), str(item["hour"]), load_font(15, bold=True))
        d.ellipse((x-8, y-8, x+8, y+8), fill=BLUE if has_rain else MUTED)
        if "label" in item:
            value = str(item["label"])
        elif "amount_mm" in item:
            value = f"{amount:g} ММ"
        else:
            value = f"{prob}%"
        centered(d, (x, y + 29), value, load_font(13, bold=True), BLUE if has_rain else MUTED)
    has_timeline_rain = any(
        bool(
            item.get(
                "has_precipitation",
                float(item.get("amount_mm", 0)) >= 0.1 or int(item.get("probability", 0)) >= 20,
            )
        )
        for item in timeline
    )
    rain_summary = "ОСАДКИ ПО ВРЕМЕНИ • СМОТРИТЕ ТАЙМ-ЛАЙН" if has_timeline_rain else "ОСАДКИ НЕ ОЖИДАЮТСЯ"
    centered(d, (W // 2, 870), rain_summary, load_font(16, bold=True), AMBER)

    stats = [
        (f"{tomorrow['pressure_mm']} ММ", "ДАВЛЕНИЕ"),
        (f"{tomorrow['wind_speed']} М/С", f"ВЕТЕР {tomorrow['wind_direction']}"),
        (f"{tomorrow['humidity']}%", "ВЛАЖНОСТЬ"),
    ]
    for box, (big, small) in zip(((122, 902, 378, 1008), (412, 902, 668, 1008), (702, 902, 958, 1008)), stats):
        glass(base, box, 20, (13, 52, 66, 185))
        cx = (box[0] + box[2]) // 2
        centered(d, (cx, 943), big, load_font(25, condensed=True))
        centered(d, (cx, 980), small, load_font(12, bold=True), PALE)
    centered(d, (W // 2, 1022), f"ВОСХОД {tomorrow['sunrise']}  •  ЗАКАТ {tomorrow['sunset']}", load_font(14, bold=True), MUTED)

    glass(base, (72, 1056, 1008, 1278), 30, (20, 29, 28, 235))
    d = ImageDraw.Draw(base)
    d.text((104, 1082), "МЕСТО ДНЯ", font=load_font(18, bold=True), fill=AMBER)
    display_name = venue.get("display_name", venue["name"].title())
    d.text((104, 1115), f"Сегодня стоит заглянуть в «{display_name}»", font=load_font(17), fill=WHITE)
    d.text((104, 1154), venue["name"], font=load_font(35, condensed=True), fill=WHITE)
    d.text((104, 1200), venue["address"].upper(), font=load_font(16, bold=True), fill=PALE)
    d.line((104, 1229, 570, 1229), fill=(AMBER[0], AMBER[1], AMBER[2], 180), width=2)
    d.text((104, 1242), f"{venue['category_label']}  •  {venue['item']}", font=load_font(15, bold=True), fill=WHITE)
    add_foreground(base, ROOT / venue["image"])

    d = ImageDraw.Draw(base)
    update_date = datetime.fromisoformat(weather["generated_at"]).strftime("%d.%m.%Y")
    d.text((72, 1310), f"ДАННЫЕ: {weather['source'].upper()} • ОБРАБОТАНО • {update_date}", font=load_font(13), fill=MUTED)
    d.text((1008, 1310), "@BAROMETR.SPB", font=load_font(14, bold=True), fill=AMBER, anchor="ra")

    output.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(output, "JPEG", quality=int(config["output"]["quality"]), optimize=True)
    manifest = {
        "asset": output.name,
        "dimensions": [W, H],
        "format": "JPEG",
        "forecast_date": tomorrow["date"],
        "weather_source": weather["source"],
        "venue": venue,
        "warnings": warnings,
    }
    manifest_path = output.with_name(output.stem + "-manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weather", type=Path, default=ROOT / "data/weather.example.json")
    parser.add_argument("--venues", type=Path, default=ROOT / "data/venues.json")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/latest.jpg")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    weather = json.loads(args.weather.read_text(encoding="utf-8"))
    venues = json.loads(args.venues.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    venue, warnings = choose_venue(venues, weather["tomorrow"]["date"], config["rotation"], args.strict)
    manifest_path = render(weather, venue, config, args.output, warnings)
    print(json.dumps({"image": str(args.output), "manifest": str(manifest_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
