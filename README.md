# CSFloat AuctionRadar

Find [CSFloat](https://csfloat.com) auctions that are about to end, ranked by how far the next bid is below the reference price.

CSFloat's sort menu lets you pick only one order at a time, for example *Best Deals* or *Expires Soon*. AuctionRadar combines the two ideas: it pulls auctions ending soon through the CSFloat API and ranks them by discount, so the best deals that are about to close come first.

> **Unofficial project.** Not affiliated with, endorsed by, or supported by CSFloat or Valve.

## How it works

1. Requests auctions (`type=auction`) up to `--max-price`, sorted by `expires_soon`.
2. Keeps the auctions that end within the next `--hours` hours.
3. Calculates the discount of the next bid against the reference price:
   - **Next bid**: the minimum bid you would have to place right now.
   - **Reference price**: CSFloat's predicted price for the item, falling back to its base price, and finally to the Steam Community Market price (marked with `*`, which tends to overstate discounts).
4. Prints the top results, best discount first, with a link to each listing.

The script only reads data. It never places bids and never touches your inventory.

## Requirements

- Python 3.8+
- [`requests`](https://pypi.org/project/requests/)
- A CSFloat API key

## Setup

```bash
git clone https://github.com/Nulerein/CSFloat_AuctionRadar.git
cd CSFloat_AuctionRadar
pip install -r requirements.txt
```

Create an API key on your CSFloat profile page (**Developer** tab) and pass it through an environment variable (recommended) or the `--key` option:

```bash
# Linux / macOS
export CSFLOAT_API_KEY="your-key"

# Windows PowerShell
$env:CSFLOAT_API_KEY = "your-key"

# Windows cmd
set CSFLOAT_API_KEY=your-key
```

> Keep your key private. Never commit it to Git or share it publicly.

## Usage

```bash
python csfloat_auctions.py --max-price 30 --hours 12 --top 15
```

| Option | Default | Description |
| --- | --- | --- |
| `--max-price` | `50` | Maximum price in USD |
| `--hours` | `24` | Only auctions ending within this many hours |
| `--min-discount` | `0` | Minimum discount in percent (use `-100` to show everything) |
| `--top` | `20` | Number of results to print |
| `--pages` | `6` | Number of pages to scan (50 listings per page) |
| `--key` | `$CSFLOAT_API_KEY` | API key |
| `--debug` | off | Print the raw JSON of the first listing |

Example output (illustrative data):

```text
Found 3; showing 3 (up to $30, ending within 12h)

 1.  +42.5%  bid $  11.50  ref $  20.00    1h 12m  float 0.1634  Example Skin | One (Field-Tested)
     https://csfloat.com/item/<listing-id>
 2.  +31.0%  bid $   6.90  ref $  10.00    4h 05m  float 0.0712  Example Skin | Two (Minimal Wear)
     https://csfloat.com/item/<listing-id>
 3.  +18.3%  bid $  24.50  ref $  30.00 *    8h 40m  float 0.2210  Example Skin | Three (Well-Worn)
     https://csfloat.com/item/<listing-id>

* CSFloat reference unavailable; compared with the Steam price (discount may be overstated)
```

## Notes and limitations

- The discount is measured against the minimum next bid. An auction can still go higher before it ends.
- Reference prices are estimates. Items with rare patterns, stickers or unusual floats can be worth very different amounts, so always check the listing yourself.
- On HTTP 429 the script waits for the time given in `Retry-After` and retries up to three times. Keep `--pages` modest.
- The `reference` and `auction_details` fields follow the live API response, which the public documentation does not fully cover. If results look empty or wrong after an API change, run with `--debug` and check the field names.
- Make sure your use complies with CSFloat's Terms of Service. This is not financial advice.

## License

[MIT](LICENSE)
