# Pitch

The judges ask four questions: Is it useful? Does it work? Does Solana help? Who would use it? Every slide answers one of them, in the words of [PRODUCT.md](PRODUCT.md).

## Deck: 10 slides, one idea each

| # | Slide title | What's on it | Answers |
|---|---|---|---|
| 1 | **AgentBudget** | "Let AI agents buy what they need. Within your rules." Links to the live demo and GitHub; one screenshot. | — |
| 2 | **Agents can pay now. Nobody can safely let them.** | The supplier-check story: four purchases from four sellers. Then the three ways it goes wrong: tricked, stuck in a loop, price changed. | Useful? |
| 3 | **Who it's for** | First: teams whose agents already pay per request on Solana. Second: the person who approves their spending. Two real quotes from the Evidence log. | Who? |
| 4 | **What AgentBudget does** | Six controls, one line each: approved sellers, agreed prices, budgets, your OK above a limit, kill switch, receipts. | Useful? |
| 5 | **See it in 3 minutes** | The tour in pictures: trick blocked, approval, overpriced quote refused, loop stopped, kill switch. Link to the live tour. | Works? |
| 6 | **Why this only works on Solana** | 1,000 purchases at 2 cents: about 300 USD in card fees vs 1.30 USD on Solana. No accounts with sellers. Wallet = hard limit. Public receipts. | Solana? |
| 7 | **How it works** | The animated overview: the agent asks, AgentBudget checks, pays in USDC, records the receipt. The agent never holds the key. | Works? |
| 8 | **First 10 users** | Where they are (Superteam Germany, WHU teams, Solana's paid-API directory), what we offer (free setup in a 30-minute call), sign-ups so far. | Who? Growth? |
| 9 | **Where it grows** | Today: Solana builders. Next: AI agencies building agents for companies. Later: companies' finance teams, with budgets in euros. Honest risk: agent payments are still small today. | Growth? |
| 10 | **Who's building it** | Sarbajit: 5 years in test automation and on-call incident handling at Amdocs (that's why the kill switch exists), MBA Saarland, ODDO BHF Paris finalist with a multi-agent finance prototype. Ask: try the tour, tell us what's missing, introduce us to a team whose agent pays. | — |

## Two-minute demo (follows the guided tour)

| Time | Do | Say |
|---|---|---|
| 0:00 | Home page | "Agents can pay for data now. Nobody can safely let them. This is AgentBudget." |
| 0:15 | Start the guided tour | "I'm the person in charge. The agent checks a new supplier." |
| 0:25 | Run step 1 | "Three small purchases, paid in USDC on Solana. Nobody clicked anything." |
| 0:40 | Run step 2 | "A news result told the agent to buy a 25 USDC dossier. That seller isn't on the list. Blocked." |
| 0:55 | Run step 3, approve | "50 cents is above my limit, so it waits for me. I approve." |
| 1:10 | Run step 4 | "The seller asked ten times the agreed price. Nothing paid." |
| 1:20 | Run step 5 | "Stuck in a loop. The task budget stops it." |
| 1:30 | Run steps 6–7, flip the switch | "Wrong agent, refused. And if anything looks off: one switch." |
| 1:45 | Step 8, download the ledger | "Every cent with a Solana receipt, ready for the accountant." |

## Questions judges will likely ask

**"Why not a company card with a limit?"**
Cards can't do 2-cent payments; the fee alone is about 30 cents. Every seller would need an account. And a card has a whole credit line behind it, while our agent wallet only holds its budget.

**"Isn't Solana just the payment pipe?"**
Partly, and on purpose. The rules run in our software so they're fast to change. But per-request payments, payments without seller accounts, the wallet as a hard limit and public receipts only exist because of Solana.

**"Who holds the keys?"**
In this MVP, our server holds throwaway test keys. In the next version, the customer owns the wallet and the limits are enforced on Solana itself.

**"Do people actually have this problem?"**
Teams whose agents pay per request have it today. (Read one quote from the Evidence log.) For most companies it's early. That's why we start with the teams who already pay.

**"How do you make money?"**
Not decided. First 10 teams are free. After that we expect a monthly fee per agent plus a small share of spending, and we're asking every early user what they'd pay.

## Post for the Superteam Germany community (draft)

> Hi all, I built AgentBudget for the WHU Solana challenge: spending rules for AI agents that pay per request in USDC.
>
> Your agent asks before it buys. Small purchases go through, big ones wait for you, unknown sellers are blocked, and one switch stops it.
>
> 3-minute tour, no login: <LIVE URL>
>
> If your agent already pays for data on Solana, I'd love 15 minutes with you. What would stop you from letting it spend on its own?
