# Plan: Thursday Oct 1 to Sunday Oct 4, 2026

Submission deadline: **Sunday 23:59**. Our target: **Sunday 20:00**.
Roles: Sarbajit = product owner and Solana prototype; Claude = backend; Lovable = frontend.

## Submission checklist (from the listing)

- [ ] Took part in the WHU hackathon 2026 (Business meets Tech, Sept 25–26): done
- [ ] Working prototype that uses Solana (USDC payments through Solana Pay Kit)
- [ ] Public GitHub repo
- [ ] Pitch deck link in the "Bounty submission link" field
- [ ] Following @SuperteamDE on X
- [ ] Based in Germany: yes

## Thursday evening

- [ ] Backend runs locally: `python -m pytest` green, then click through `/docs`
- [ ] Paste [LOVABLE_PROMPT.md](LOVABLE_PROMPT.md) into Lovable; check Home, Connect and Early access with sample data
- [ ] Create the public GitHub repo and push

## Friday

- [ ] Solana prototype: real USDC payments on the test network (owner: Sarbajit)
- [ ] Deploy: Supabase, then Render (Blueprint), then point Lovable at the API
- [ ] Run the guided tour end to end on the live URL, on a laptop and on a phone
- [ ] Post the community message from [PITCH.md](PITCH.md) and ask for 15-minute calls

## Saturday

- [ ] Three conversations with agent builders or spending approvers; write each into the Evidence log in [PRODUCT.md](PRODUCT.md)
- [ ] Fix whatever confused people in the tour (copy lives in `app/tour.py`)
- [ ] Record the 2-minute demo video (backup if the server is slow during judging)
- [ ] Fill in the live URLs in the README

## Sunday

- [ ] Build the 10-slide deck from [PITCH.md](PITCH.md), with real quotes on slide 3 and the sign-up count on slide 8
- [ ] Final check in a private browser window; wake both Render services
- [ ] Submit by 20:00
