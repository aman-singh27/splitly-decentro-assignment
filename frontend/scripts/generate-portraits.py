"""Create original, consistent monochrome SVG portraits. No reference-image pixels used."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / 'public' / 'portraits'
ROOT.mkdir(parents=True, exist_ok=True)
HAIR = [
 'M22 35Q17 12 34 12Q52 5 63 20L64 35L58 30Q58 22 53 21L27 26L26 36Z',
 'M21 42L20 25Q18 6 40 9Q62 7 64 29L63 43L57 32L55 22Q39 34 27 24L27 38Z',
 'M22 33L21 22L28 23L30 11L38 18L45 7L50 19L60 14L59 30L56 34L54 25L30 25L27 35Z',
 'M20 49Q11 43 19 35Q11 27 20 24Q12 17 23 14Q24 6 33 11Q40 2 47 11Q57 6 60 16Q72 17 64 26Q74 36 62 43L57 33L55 23L29 24L27 36Z',
 'M19 58L18 26Q18 8 41 8Q63 8 65 28L64 59L55 55L55 29Q42 33 27 26L26 55Z',
 'M23 31Q17 15 30 14Q36 2 42 14Q59 9 62 31L56 30Q40 20 27 31Z',
 'M20 35Q19 16 31 11Q46 6 60 17L64 35L58 34L54 23L28 25L27 36Z',
 'M20 49L19 24Q18 10 32 11Q37 2 46 9Q64 9 64 30L66 48L57 47L56 29L44 21L29 30L28 48Z'
]
for index in range(16):
 hair = HAIR[index % 8]
 glasses = '<g fill="none"><rect x="26" y="34" width="13" height="10" rx="4"/><rect x="43" y="34" width="13" height="10" rx="4"/><path d="M39 38H43M22 36L26 38M56 38L60 36"/></g>' if index in (1,5,8,12) else ''
 facial = '<path d="M31 50Q41 61 52 50Q48 61 41 62Q33 59 31 50Z" fill="#171a15"/>' if index in (6,10,14) else ''
 shirt = '<path d="M14 82Q14 66 31 63L41 70L51 63Q68 66 68 82Z" fill="#171a15"/><path d="M34 65L41 73L48 65" stroke="#fff" fill="none"/>' if index % 3 == 0 else '<path d="M12 82Q13 65 32 63L41 69L50 63Q69 66 70 82Z" fill="#fff"/><path d="M23 73V81M60 73V81"/>'
 svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 82 82"><rect width="82" height="82" fill="#fff"/><g stroke="#171a15" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{shirt}<path d="M33 55V64Q41 72 49 64V55" fill="#fff"/><ellipse cx="23" cy="39" rx="4" ry="6" fill="#fff"/><ellipse cx="59" cy="39" rx="4" ry="6" fill="#fff"/><path d="M23 28Q24 15 41 15Q58 15 59 29L57 45Q53 59 41 60Q28 57 25 45Z" fill="#fff"/><path d="{hair[3:] if False else hair}" fill="#171a15"/><path d="M29 32L35 31M46 31L52 32" fill="none"/><path d="M40 37L38 44H42M35 49Q41 53 47 49" fill="none"/>{facial}<circle cx="32" cy="38" r="1.3" fill="#171a15" stroke="none"/><circle cx="49" cy="38" r="1.3" fill="#171a15" stroke="none"/>{glasses}</g></svg>'
 (ROOT / f'portrait-{index+1:02}.svg').write_text(svg, encoding='utf-8')
