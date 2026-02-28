from __future__ import annotations

from datetime import datetime, timezone

from data.article_generator import generate_article, list_technology_stems


def _select_rotating_stem() -> str | None:
    stems = [item.get("stem") for item in list_technology_stems() if item.get("stem")]
    if not stems:
        return None

    day_index = datetime.now(timezone.utc).timetuple().tm_yday
    return stems[day_index % len(stems)]


def main() -> int:
    print("Generating roundup article...")
    roundup = generate_article()
    print(f"Created roundup article: {roundup.get('id')}")

    stem = _select_rotating_stem()
    if stem:
        print(f"Generating rotating technology article for: {stem}")
        tech_article = generate_article(tech_stem=stem)
        print(f"Created tech article: {tech_article.get('id')}")
    else:
        print("No technology stems found; skipped rotating technology article.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
