# Sanctions List Tracker

A tool that checks four official sanctions lists every day and records who was added, who was removed and whose listing was changed. The results are shown on a Streamlit dashboard, which also compares the lists with each other.

| List | Publisher | Format |
|---|---|---|
| UK Sanctions List | Foreign, Commonwealth and Development Office (FCDO) | CSV |
| SDN and Consolidated (non-SDN) Lists | US Treasury, Office of Foreign Assets Control (OFAC) | Six legacy CSV files |
| Consolidated List | UN Security Council | XML |
| Consolidated Financial Sanctions List | European Commission | CSV |

HM Treasury's OFSI Consolidated List is not tracked separately: it closed on 28 January 2026 and UK designations are now published only on the FCDO's UK Sanctions List.

## Why I built it

Screening is only as good as the list you screen against. Each of these lists changes several times a week. Compliance teams need to know quickly when a new person or company is designated so they can check whether any customers match, and when a listing is amended with a new alias or a wider set of sanctions. Firms that operate across borders screen against several lists at once, and the lists do not line up: a person sanctioned by the US may not be sanctioned by the UK or the EU.

This project complements my [Sanctions Screening Tool](https://github.com/Srikanth-nallabilli/sanctions-screening-tool). That tool checks names against a list. This one keeps track of how the list itself is changing.

## What it does

- Downloads each list once a day using a scheduled GitHub Action
- Turns every list into the same layout, one record per designation, so a person with five aliases counts once
- Compares today's list with the previous run and classes each change as Added, Removed or Amended
- For amendments, records which fields changed, such as aliases, sanctions imposed, nationality or the statement of reasons
- Keeps a running change log and a daily summary for each list in `data/<list>/`, committed back to the repository
- Opens a GitHub issue listing the day's changes whenever a list changes, so the owner gets an email alert
- Matches listings across the four lists to show where they overlap and where they differ

## Dashboard

A picker at the top switches every tab between the UK, US (OFAC), UN and EU lists.

| Tab | What it shows |
|---|---|
| Overview | New designations per month with key events marked, a world map, regimes, nationalities and the sanctions most often imposed |
| Recent activity | Listings newly designated or amended by the publisher in the last 30, 90 or 180 days |
| Daily changes | Each day's additions, removals and amendments found by the tracker, with a download of the full log |
| Shadow fleet | The designated ships: current flags, flag hopping, ship types, fleet age, and a searchable register by IMO, flag or owner |
| Data quality | How complete the identifying details are for individuals, entities and ships, and which listings would be hardest to clear as false positives |
| Search the list | Find a name or alias, filter by regime and type, and see a listing's change history |
| Compare lists | How much of each list appears on the others, and the designations on one list that cannot be found on another |

## Why the shadow fleet and data quality views

Ships are one of the fastest growing parts of the list. Vessels moving Russian oil outside the price cap change flag and owner to avoid scrutiny, so a ship's flag history matters as much as its name, and the IMO number is the identifier that never changes.

Data quality matters because screening is a two step job. A system flags a possible name match, then an analyst uses date of birth, nationality and ID numbers to decide whether it is the real person. Listings with only a name produce alerts that are slow and difficult to close, so knowing where the list is thin helps a team plan its screening rules.

## How it works

```
tracker/uksl.py  (UK CSV)     \
tracker/ofac.py  (OFAC CSVs)   \   one row per        diff()       data/<list>/changes.csv
tracker/un.py    (UN XML)      /   designation,  ->  (Added,   ->  data/<list>/runs.csv
tracker/eu.py    (EU CSV)     /    same columns       Removed,     data/<list>/latest.csv.gz
                                                      Amended)
```

`tracker/sources.py` lists the four sources, `tracker/common.py` holds the shared columns and the daily comparison, and `tracker/compare.py` matches listings across lists.

A few design choices worth noting:

- **Each publisher's own identifier as the key.** The FCDO Unique ID for the UK list (the FCDO asks firms to use it rather than the retired OFSI Group ID), the OFAC entity number, the UN permanent reference number (such as QDi.001) and the EU's logical ID.
- **One list failing does not stop the others.** Each list is downloaded and saved separately. If a publisher's site is down, the run is marked as failed but the other lists are still updated and alerted.
- **Same layout for every list.** OFAC writes dates of birth, nationalities and IMO numbers into a free text remarks field, the EU repeats each person on dozens of rows, and the UN uses XML. Each parser turns its list into the same columns, leaving a field blank when the publisher does not provide it.
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

Changes appear from the second daily run onwards. To update one list only, use `--source` (`uk`, `ofac`, `un` or `eu`), for example `python -m tracker.update --source un`. You can also run the update against a file you have downloaded yourself with `python -m tracker.update --source uk --file UK-Sanctions-List.csv`. For OFAC, `--file` takes a folder containing `sdn.csv`, `alt.csv`, `add.csv`, `cons_prim.csv`, `cons_alt.csv` and `cons_add.csv`.

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

The tests use small made-up lists in the same layouts as the published files. They cover title row handling, grouping of aliases, listings with no primary name, ship fields, detection of each change type, same day re-runs, the alert text, the run history and the bad download check. For the OFAC, UN and EU files they also cover reading the remarks field, merging listings that appear on two OFAC lists, choosing a Latin-script name on the EU list, one list failing without stopping the others, and matching listings across lists.

## Limitations

- The tracker sees the list once a day, so two updates published on the same day are recorded as one set of changes.
- The name search is a simple text match for exploring the list. It is not a screening tool and does not replace fuzzy matching.
- History starts from the first run. Earlier changes are not reconstructed.
- If a publisher changes its file layout, that list's parser stops with a clear error rather than recording false changes.
- OFAC does not publish designation dates, so the date charts are not available for the US list. Its history starts from the tracker's first run.
- The EU file does not list vessels, and the UN list has very few, so the shadow fleet view is most useful for the UK and US lists.
- Matching across lists is strict on purpose (UN reference, IMO number, or an exact name or alias after ignoring case, accents, punctuation and word order). A name spelt differently on two lists shows as a gap unless one list carries the other spelling as an alias. The EU file rarely includes the UN reference number, so some UN-derived EU listings with one-word names are not matched.

## Data sources

- [The UK Sanctions List](https://www.gov.uk/government/publications/the-uk-sanctions-list), Foreign, Commonwealth and Development Office. Contains public sector information licensed under the Open Government Licence v3.0.
- [OFAC Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service), US Department of the Treasury. A US government work in the public domain.
- [United Nations Security Council Consolidated List](https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list), United Nations.
- [Consolidated list of persons, groups and entities subject to EU financial sanctions](https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions), European Commission. Reuse is authorised under Commission Decision 2011/833/EU.
