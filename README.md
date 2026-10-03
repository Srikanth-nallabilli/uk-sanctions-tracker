# UK Sanctions List Change Tracker

A tool that checks the UK Sanctions List every day and records who was added, who was removed and whose listing was changed. The results are shown on a Streamlit dashboard.

## Why I built it

Screening is only as good as the list you screen against. The UK Sanctions List, published by the FCDO, changes several times a week, and since the OFSI Consolidated List closed on 28 January 2026 it is the only official source for UK sanctions designations. Compliance teams need to know quickly when a new person or company is designated so they can check whether any customers match, and when a listing is amended with a new alias or a wider set of sanctions.

This project complements my [Sanctions Screening Tool](https://github.com/Srikanth-nallabilli). That tool checks names against a list. This one keeps track of how the list itself is changing.

## What it does

- Downloads the official UK Sanctions List CSV once a day using a scheduled GitHub Action
- Groups the name rows into one record per designation using the FCDO Unique ID, so a person with five aliases counts once
- Compares today's list with the previous run and classes each change as Added, Removed or Amended
- For amendments, records which fields changed, such as aliases, sanctions imposed, nationality or the statement of reasons
- Keeps a running change log and a daily summary in the `data` folder, committed back to the repository

## Dashboard

| View | What it shows |
|---|---|
| Headline figures | Size of the list and the number of additions, removals and amendments in the latest run |
| Latest changes | Every change on a chosen date, filterable by type, with a download of the full log |
| History | Changes per day and the size of the list over time |
| By regime | Current designations by regime and type, and which regimes have seen the most changes |
| Search a name | Look up a name or alias on the current list and see its change history |

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
4. Deploy `app.py` on [Streamlit Community Cloud](https://share.streamlit.io). The dashboard picks up new data each time the Action commits.

## Tests

```bash
python -m pytest
```

The tests use small made-up lists in the same layout as the published file. They cover title row handling, grouping of aliases, detection of each change type, the run history and the bad download check.

## Limitations

- The tracker sees the list once a day, so two updates published on the same day are recorded as one set of changes.
- The name search is a simple text match for exploring the list. It is not a screening tool and does not replace fuzzy matching.
- History starts from the first run. Earlier changes are not reconstructed.
- If the FCDO changes the column headings, the parser stops with a clear error rather than recording false changes.

## Data source

[The UK Sanctions List](https://www.gov.uk/government/publications/the-uk-sanctions-list), Foreign, Commonwealth and Development Office. Contains public sector information licensed under the Open Government Licence v3.0.
