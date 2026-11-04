# Sentimientos - Ras Manuel
Its own project: everything here comes from this song's lyrics only (lyrics.txt).

v1 (images\v1) was rejected 2026-10-23: it showed the singer acting the lyrics out literally. Justice: art is an extended metaphor that makes you feel the specific details without showing the subject.

## v2 metaphor: La laguna
What lives inside him as a dark lagoon full of light that only shows when something moves it. The feelings speak and glow and cannot be hidden (dentro de mi hablan y hablan, no los voy a callar). The storm of negativity only makes the water shine brighter (no more negativity). The mangrove roots carry the light from water to tree like veins (Pachamama, somos energia, somos vibracion). The fish turn together in a spiral of light for protection, like a family and like a dance (I dance for protection, blessings para mi familia, cierra tus dos manos en conexion).

## Art style
**Luminous chalk pastel on black paper.** Light drawn by hand out of black paper is the feeling of something inside coming to the surface. It's intimate and textured, not slick.

Style sentence (word for word in every prompt):

soft chalk pastel drawing on black paper, luminous blue-green strokes glowing against the black, velvety pigment texture and the fine grain of the paper

Recurring element (word for word):

a black mangrove lagoon at night

## The 5 pictures (v2)
### 1. gota
Lyric: Close my eyes and check inside of me

A single drop falls onto the perfectly still surface of a black mangrove lagoon at night and a ring of glowing blue-green light spreads outward from where it lands, stars reflected in the dark water around it, soft chalk pastel drawing on black paper, luminous blue-green strokes glowing against the black, velvety pigment texture and the fine grain of the paper. Low view just above the water, the glowing ring centered, the black silhouettes of mangrove trees along the far shore. The glowing ring as the main light, colors of electric blue-green, deep black and faint star white, no people, no text, no watermark.

### 2. hablan
Lyric: Dentro de mi hablan y hablan, no los voy a callar

Beneath the dark surface of a black mangrove lagoon at night, swirling currents of blue-green light rise and twist up from the depths like voices, while the surface above stays black and calm under the stars, soft chalk pastel drawing on black paper, luminous blue-green strokes glowing against the black, velvety pigment texture and the fine grain of the paper. Split-level view half above and half below the waterline, the calm night above and the glowing currents filling the lower half. The currents as the only light, colors of electric blue-green, teal, black and star white, no people, no text, no watermark.

### 3. tormenta
Lyric: Tired of this reality / No more negativity

A storm wind tears across a black mangrove lagoon at night and every breaking wave crest ignites in bright blue-green light, heavy black clouds pressing down from above, soft chalk pastel drawing on black paper, luminous blue-green strokes glowing against the black, velvety pigment texture and the fine grain of the paper. Wide view at water level, rows of glowing waves rolling toward the camera, the mangrove shore dark behind. The waves as the only light, colors of electric blue-green, white foam, storm charcoal and black, no people, no text, no watermark.

### 4. raices
Lyric: Pachamama, yo te pido perdon / somos energia, somos vibracion

The tangled roots of a mangrove tree reach down into a black mangrove lagoon at night, and threads of blue-green light travel up through the roots and into the trunk like veins, joining the water to the tree, soft chalk pastel drawing on black paper, luminous blue-green strokes glowing against the black, velvety pigment texture and the fine grain of the paper. Close medium view at water level, the roots arching across the frame, their reflections glowing below. The light inside the roots as the main light, colors of blue-green, deep black, dark bark brown and soft silver, no people, no text, no watermark.

### 5. danza
Lyric: I dance for protection / blessings para mi familia / cierra tus dos manos en conexion

A school of small silver fish turns together in a tight spiral beneath the surface of a black mangrove lagoon at night, their movement leaving swirling trails of blue-green light that form a glowing circle, soft chalk pastel drawing on black paper, luminous blue-green strokes glowing against the black, velvety pigment texture and the fine grain of the paper. View from directly above looking down into the water, the spiral centered, black water all around. The fish trails as the only light, colors of electric blue-green, silver and black, no people, no text, no watermark.

## Files
Comfort job `song_sentimientos_v2` renders to `out\song_sentimientos_v2\`; copies (with _sheet.jpg, _prompts.txt, _manifest.json = seeds) in `images\v2\`.
Size 1376x768 = H3 video size. Upscale only the ones Justice picks (same #seed + #final).


---
# v4 (2026-10-23): research-picked art style, no photorealism
Justice rejected v1-v3: too realistic, and the styles weren't backed by research. v4 style chosen from download rankings of the 1,500+ Krea 2 style LoRAs on Hugging Face (ilkerzgi), checked against Creative Boom's 2026 top-illustrators survey.

**Airy gouache minimalist: #28 by downloads and among the most-liked style LoRAs (4 likes). It's also the flat, open-space gouache look of the top illustrators in Creative Boom's 2026 survey of 1,000+ creatives (Tom Haugomat, Malika Favre). Quiet open space suits an inward song.**

LoRA: `airy-gouache-minimalist-comfy.safetensors` at 1.1, trigger `airy gouache minimalist style` at the end of every prompt.

Style sentence: airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette

### 1. adentro
Lyric: Close my eyes and check inside of me

A tiny figure sits cross-legged on top of a round green hill with eyes closed while soft concentric rings of light ripple outward from them into a vast pale sky, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the hill low in the frame and the figure small at its peak, the rings filling the sky. Soft dawn light, colors of sage green, peach, cream and soft lilac, no text, no watermark, airy gouache minimalist style.

### 2. hablan
Lyric: Dentro de mi hablan y hablan, no los voy a callar

A small house alone on a plain at night with a single warm lit window, and from that window ribbons of color flow out and curl across the dark blue sky like voices, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the house small in the lower center, the ribbons sweeping across the sky. Warm window glow against cool night, colors of deep blue, warm yellow, coral and teal, no people, no text, no watermark, airy gouache minimalist style.

### 3. manos
Lyric: Cierra tus dos manos en conexion / Somos energia

Two open hands cupped together hold a tiny glowing sun, its warm light spilling between the fingers, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Close centered view of the hands against a plain soft background with open space all around. Warm glow from the little sun, colors of terracotta, golden yellow, cream and soft rose, no text, no watermark, airy gouache minimalist style.

### 4. pachamama
Lyric: Pachamama, yo te pido perdon

A long range of green hills whose outline forms the profile of a sleeping woman's face looking up at a pale moon, small trees and a river across the slopes, and a tiny figure kneeling at the foot of the hills with forehead to the ground, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the hills stretching across the frame, the figure small on the lower right. Soft moonlight, colors of earth ochre, moss green, dusty blue and cream, no text, no watermark, airy gouache minimalist style.

### 5. danza
Lyric: I dance for protection / somos vibracion

A small figure dances on the still surface of a lake at dusk, arms raised mid-spin, and every step sends rings of color spreading across the water in widening circles, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the figure small in the center, the rings filling the lake, distant hills along the horizon. Soft dusk light, colors of lilac, coral, teal and cream, no text, no watermark, airy gouache minimalist style.

Files: `out\song_sentimientos_v4\`, copies in `images\v4\`.

---
# v5 (2026-10-23): built from what Justice picked (see README section 6)
LoRA `airy-gouache-minimalist-comfy.safetensors` at 1.1, trigger `airy gouache minimalist style`. Style sentence: airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette

### 1. orilla
Lyric: Dentro de mi hablan y hablan, no los voy a callar

A small simple figure in a plain white shirt and trousers stands at the edge of a vast calm sea at dusk, and soft ribbons of colored light rise from their chest and drift up into the sky, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the figure tiny in the lower center, the ribbons curling up across the open sky. Soft dusk light, colors of coral, teal, lilac and cream, no text, no watermark, airy gouache minimalist style.

### 2. arbol
Lyric: Pachamama / somos energia

A single round tree stands on a gentle hill, and under the ground in a cutaway its roots glow with warm light that flows up the trunk and into its leaves, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the tree centered, the glowing roots spreading wide below the grass line. Soft evening light, colors of earth ochre, golden yellow, sage green and dusty blue, no people, no text, no watermark, airy gouache minimalist style.

### 3. bote
Lyric: Close my eyes and check inside of me

A small wooden boat with a lit lantern rests on a perfectly still lake at night, and rings of soft light spread out across the water from where it floats, stars reflected all around, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view from a slightly high angle, the boat small in the center, the rings filling the lake. Warm lantern glow against deep blue night, colors of deep blue, warm yellow, teal and cream, no people, no text, no watermark, airy gouache minimalist style.

### 4. circulo
Lyric: Blessings para mi familia / cierra tus dos manos en conexion

A family of small simple figures in plain clothes holds hands in a circle on top of a green hill, and rings of soft light spread outward from their circle across the land and sky, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view, the circle small at the top of the hill, the rings filling the frame. Soft sunrise light, colors of sage green, peach, cream and soft gold, no text, no watermark, airy gouache minimalist style.

### 5. cielo
Lyric: Escucho otra frecuencia para mi corazon / somos vibracion

A small simple figure in plain clothes lies on their back in a field of tall grass with eyes closed, and the whole sky above is filled with wide soft concentric ripples like rings on water, airy minimalist gouache illustration, flat matte color shapes, soft paper grain, lots of open space and a calm limited palette. Wide view from above the grass line, the figure small in the lower third, the rippling sky taking the rest. Calm afternoon light, colors of pale blue, cream, sage and soft lilac, no text, no watermark, airy gouache minimalist style.

Files: `out\song_sentimientos_v5\`, copies in `images\v5\`.
