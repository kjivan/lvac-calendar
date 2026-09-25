# LVAC Calendar

A subscribable calendar of Las Vegas Athletic Club classes at the **Northwest** and **Southwest**
clubs: Cycle, Cycle Xpress, BodyPump, BodyPump Xpress, BodyBalance and LVAC's yoga classes
(Beginning, Gentle, Gentle Mix, Yin, Yoga, Blend, Vinyassa Flow and All Levels).

**Feed URL:** https://kjivan.github.io/lvac-calendar/lvac-classes.ics

## How it works

Once a day (early morning Pacific time) a GitHub Actions workflow downloads the schedule data behind
[LVAC's class search](https://www.lvac.com/locations/search-class-schedules), rebuilds
`docs/lvac-classes.ics` and publishes it with GitHub Pages.

- Class times are in Pacific time. Calendar apps show them in your device's time zone.
- The feed has only classes LVAC has actually published, usually about 8 days ahead.
- Past classes stay in the feed for 30 days.
- A run commits only when the schedule changes. If LVAC's data can't be read, the run fails,
  GitHub emails you, and the last good feed stays up.

## Subscribe in Apple Calendar

1. **File → New Calendar Subscription…** and paste the feed URL.
2. Set **Location** to **iCloud** so it syncs to your iPhone, and **Auto-refresh** to **Every hour**.

## Change what's included

Edit `LOCATIONS` and `CLASS_NAMES` at the top of `lvac_calendar.py`, then push. The workflow runs
on every push, or trigger it from the **Actions** tab (**Update LVAC calendar → Run workflow**).

```bash
python -m unittest                          # tests
python lvac_calendar.py docs/lvac-classes.ics  # build locally
```
