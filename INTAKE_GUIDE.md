# Safe evidence intake

You do not need to have everything ready at once. Start with a small, public, non-sensitive batch.

## First batch

Create `targets.txt` with one public URL per line. Good first items are:

- official city or county pages
- public meeting minutes and agendas
- public procurement or budget pages
- public CourtConnect case pages or permitted filings
- public Arkansas business filings
- official public statements or public videos

Add comments beginning with `#` to explain why each URL matters. Do not add passwords, login links, private-group links, medical or CPS records, child information, sealed material, leaked files, or privileged communications.

## If you have documents but they are not organized

Keep the originals in a separate folder. Make a simple inventory with:

- your own filename
- neutral description
- approximate date
- source or sender category
- whether it is public, authorized, restricted, or unknown
- whether counsel has reviewed it

Do not rename or edit originals. Do not upload sensitive originals to this workspace. Use a neutral reference such as `restricted-item-001` in the casefile and ask counsel how to preserve the underlying material.

## If you have screenshots or videos

Record the original URL, account or issuing body, post date, capture date/time and timezone, and what the item visibly establishes. Preserve the original file separately when lawful. Screenshots and clips are not automatically authentic or complete.

## If you have notes or a timeline

Write observations as facts you personally observed or exact quotations. Mark memory, interpretation, allegation, and unknown separately. Include facts that may weaken the concern and possible innocent explanations.

## First command

After reviewing the URL list with counsel:

```bash
python3 collector.py targets.txt --output evidence/raw
```

The collector records access results, timestamps, and hashes. It does not follow links or bypass restrictions.

## Stop and ask counsel first

Stop before transfer if an item involves children, CPS, medical or disability information, school records, sealed court material, confidential legal communications, credentials, leaked data, or a court order. Retain only minimal routing metadata and do not forward the underlying content.
