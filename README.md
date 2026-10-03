# UK Sanctions List Change Tracker

A tool that checks the UK Sanctions List every day and records who was added, who was removed and whose listing was changed. The results are shown on a Streamlit dashboard.

## Why I built it

Screening is only as good as the list you screen against. The UK Sanctions List, published by the FCDO, changes several times a week, and since the OFSI Consolidated List closed on 28 January 2026 it is the only official source for UK sanctions designations. Compliance teams need to know quickly when a new person or company is designated so they can check whether any customers match, and when a listing is amended with a new alias or a wider set of sanctions.

This project complements my [Sanctions Screening Tool](https://github.com/Srikanth-nallabilli/sanctions-screening-tool). That tool checks names against a list. This one keeps track of how the list itself is changing.

## What it does

- Downloads the official UK Sanctions List CSV once a day using a scheduled GitHub Action
- Groups the name rows into one record per designation using the FCDO Unique ID, so a person with five aliases counts once
- Compares today's list with the previous run and classes each change as Added, Removed or Amended
- For amendments, records which fields changed, such as aliases, sanctions imposed, nationality or the statement of reasons
- Keeps a running change log and a daily summary in the `data` folder, committed back to the repository
- Opens a GitHub issue listing the day's changes whenever the list changes, so the owner gets an email alert

## Dashboard

| Tab | What it shows |
|---|---|
| Overview | New designations per month with key events marked, a world map, regimes, nationalities and the sanctions most often imposed |
| Recent activity | Listings newly designated or amended by the FCDO in the last 30, 90 or 180 days |
| Daily changes | Each day's additions, removals and amendments found by the tracker, with a download of the full log |
| Shadow fleet | The designated ships: current flags, flag hopping, ship types, fleet age, and a searchable register by IMO, flag or owner |
| Data quality | How complete the identifying details are for individuals, entities and ships, and which listings would be hardest to clear as false positives |
| Search the list | Find a name or alias, filter by regime and type, and see a listing's change history |

## Why the shadow fleet and data quality views

Ships are one of the fastest growing parts of the list. Vessels moving Russian oil outside the price cap change flag and owner to avoid scrutiny, so a ship's flag history matters as much as its name, and the IMO number is the identifier that never changes.

Data quality matters because screening is a two step job. A system flags a possible name match, then an analyst uses date of birth, nationality and ID numbers to decide whether it is the real person. Listings with only a name produce alerts that are slow and difficult to close, so knowing where the list is thin helps a team plan its screening rules.

## How it works

```
GOV.UK CSV  ->  read_raw()  ->  to_designations()  ->  diff()  ->  data/changes.csv
                (skips title    (one row per          (Added,      data/runs.csv
                 rows, maps      Unique ID)            Removed,     data/latest.csv.gz
                 headings)                             Amended)
```

A few design choices worth noting:

- **Unique ID as the key.** The FCDO asks firms to use the Unique ID rather than the retired OFSI Group ID, so the tracker does the same.
- **Amendments are field level.** Each tracked field is compared separately, so the log says what changed rather than just that something changed. Long text fields such as the statement of reasons are compared by fingerprint to keep the stored data small.
- **Bad download protection.** If the list suddenly shrinks by more than half, the run stops and the history is left untouched, since a broken download is far more likely than a mass de-listing.
- **Same day re-runs are safe.** Running the check twice on one day adds to that day's totals rather than double counting or resetting them.
- **New fields do not cause false alerts.** Only fields stored on both days are compared, so adding a new field to the tracker never marks every listing as amended.
- **No ID numbers stored.** For passports, national IDs and business registrations the tracker only records whether one is listed, not the number itself.
- **Small storage.** Only the latest processed list is stored, not a copy of every day's 30MB file, so the repository stays light.

## Running it locally

```bash
pip install -r requirements.txt
python -m tracker.update      # first run saves a baseline
streamlit run app.py
```

Changes appear from the second daily run onwards. You can also run the update against a file you have downloaded yourself with `python -m tracker.update --file UK-Sanctions-List.csv`.

## Deploying

1. Push the repository to GitHub.
2. Under Settings, Actions, General, set workflow permissions to "Read and write" so the daily job can commit its results.
3. Run the "Daily sanctions list check" workflow once by hand from the Actions tab to save the baseline.
4. Alerts arrive as GitHub issues assigned to the repository owner. Make sure email notifications for assigned issues are on in your GitHub notification settings.
5. Deploy `app.py` on [Streamlit Community Cloud](https://share.streamlit.io). The dashboard picks up new data each time the Action commits.

## Tests

```bash
python -m pytest
```

The tests use small made-up lists in the same layout as the published file. They cover title row handling, grouping of aliases, listings with no primary name, ship fields, detection of each change type, same day re-runs, the alert text, the run history and the bad download check.

## Limitations

- The tracker sees the list once a day, so two updates published on the same day are recorded as one set of changes.
- The name search is a simple text match for exploring the list. It is not a screening tool and does not replace fuzzy matching.
- History starts from the first run. Earlier changes are not reconstructed.
- If the FCDO changes the column headings, the parser stops with a clear error rather than recording false changes.

## Data source

[The UK Sanctions List](https://www.gov.uk/government/publications/the-uk-sanctions-list), Foreign, Commonwealth and Development Office. Contains public sector information licensed under the Open Government Licence v3.0.
