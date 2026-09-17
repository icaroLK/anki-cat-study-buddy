# 🐱︎ Cat Study Buddy ᗢᘏᓗ

An Anki addon that adds a virtual cat companion to Anki's main screen and review screen. The cat's mood reacts to how many cards you study each day, and it plays a quick reaction animation after every answer during review.

## Features

- **Mood ladder:** Sad → Neutral → Happy → Excited, based on how many cards you've studied today, with animation sets and card-count thresholds you control for each step.
- **Mini cat during review:** Idles between cards, then reacts for 2 seconds to your answer (happy on Good/Hard/Easy, sad/exaggerated on Again).
- **Optional mood bar:** Shows the mood label, a progress bar, and today's card count under the cat.
- **Pick a name and color:** `classical` (cream), `orange`, `grey`, or `white` — or let the color re-roll randomly every time Anki starts.
- **Adjustable sprite size** and mood thresholds.
- A native settings dialog through "**Tools → Cat Study Buddy Settings…**" (no manual JSON editing needed)

## Screenshots

**Cat on the main screen** - Sits quietly below your deck list:

![Deck list with cat](screenshots/deck-list-with-cat.jpg)

**Mood reacts to how much you've studied today** - Sad, Neutral, Happy, Excited, each with its own animation set:

| Sad | Neutral | Happy | Excited |
|---|---|---|---|
| ![Sad](screenshots/mood-sad.jpg) | ![Neutral](screenshots/mood-neutral.jpg) | ![Happy](screenshots/mood-happy.jpg) | ![Excited](screenshots/mood-excited.jpg) |

**Random action animations** - Once Happy, the cat also plays extra idle actions like eating, napping in a box, or a bath:

![Cat eating](screenshots/cat-eating.jpg)

**Mini cat during review** - Idles between cards and reacts to your answer:

![Mini cat during review](screenshots/mini-cat-during-review.jpg)

**Settings dialog** - No manual config editing required:

![Settings dialog](screenshots/settings-dialog.jpg)

## Installation

**From AnkiWeb:** *[Anki Shared Addons](https://ankiweb.net/shared/info/94808647)* <br>
**Code:** `94808647`

## Configuration

Open **Tools → Cat Study Buddy Settings…** for a checkbox/dropdown UI, or edit the config directly via **Tools → Add-ons → Config**:

| Option | Default | Description |
|---|---|---|
| `pet_name` | `Mochi` | Your cat's name. |
| `pet_color` | `classical` | One of `classical` (cream), `orange`, `grey`, `white`. |
| `pet_color_random` | `false` | Re-roll `pet_color` to a random one of the four every time Anki starts (and immediately when checked in settings). |
| `mood_neutral_at` | `50` | Cards/day where mood moves from Sad to Neutral. |
| `mood_happy_at` | `100` | Cards/day where mood moves from Neutral to Happy. |
| `mood_excited_at` | `200` | Cards/day where mood moves from Happy to Excited. |
| `sprite_size` | `100` | How big the cat renders, in pixels. |
| `show_during_review` | `true` | Show the mini cat in the corner during reviews. |
| `show_mood_bar` | `true` | Show the mood label, bar, and today's card count. |

## License

MIT - see [LICENSE](LICENSE).
