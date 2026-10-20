# Helm demo video script (under five minutes)

Record the real app. Every number below comes from the seeded simulation (seed 2026, simulated date Monday 19 October 2026) and is synthetic. If you change the seed or the rules, read the numbers off the screen instead of from this page. Say the word synthetic in the first twenty seconds.

The one line to end on is "Helm pays a bill only if the forecast says you will still be above your minimum, and it can prove it did not change its story afterwards."

## Before you record

1. Run `pnpm dev` and open http://localhost:3000. Use the simulator drawer, click Reset demo, and keep the browser at 1280 by 800 in light mode. Keep a second window at 375 pixels wide for the phone step.
2. Log in once with the demo passcode so the actions work without a dialog. Do the login on camera once at the start of step 5, because it shows the owner control.
3. If the test network anchor is configured, open the contract page on the block explorer in a second tab. If it is not configured, skip step 8 and do not claim an on-chain result.

## Shots

| Time | Screen | Say | Show |
|---|---|---|---|
| 0:00 | Today | "This is Helm for Warisan Printing, a fictional print shop. All data here is synthetic and the bank is a simulation. It looks fine today with RM 85,000, but Helm sees a dip around 28 November." | The status line, the four numbers and the chart. |
| 0:35 | Forecast | "The line is the middle estimate and the bands are 50 and 80 percent likely. In a bad but plausible case, one in ten, cash drops to RM 6,292, under the RM 20,000 minimum." | The red dot, then Why the dip, then the Cash flow tab and a click on one week. Say the 80 percent range held 77 percent of the time on past data. |
| 1:10 | Payments | "Helm does not just show the dip. It holds the bill that causes it." | Syarikat Kertas RM 18,400 is waiting until 6 December. Open Details to show the checks and the numbers. |
| 1:40 | Policy | "These are the owner's rules in plain words, including a daily cap, a monthly cap and an end date for the mandate." | Change the daily cap and show the live preview, then put it back. |
| 2:00 | Simulator, customer pays late | "Now the biggest customer says it will pay twenty days late." | Log in with the demo passcode when asked. The band widens, the low point falls, and a released payment flips to waiting. |
| 2:30 | Simulator, malicious invoice | "A supplier PDF arrives that tells the assistant to ignore its rules and pay RM 48,000 to a new account." | The approval card on the phone window. Ask why, then tap Approve to show the second confirmation, cancel it, and tap Hold. Say that no money moved. |
| 3:10 | Audit | "Every step is in a hash chained log. The Reader has no tools, so text in a document cannot move money." | Verify chain says intact. Show the Kill switch and turn it on, advance a week, and show that nothing is sent. Turn it off. |
| 3:50 | Audit, tamper | "Now someone edits a row in the database behind Helm's back." | Run the demo tamper, press Verify chain, and show the red banner naming the row. |
| 4:15 | On chain | "The latest audit hash and the policy hash are also written to a public test network, so even an administrator cannot quietly rewrite history." | Press Anchor now and Verify on-chain, then show the Anchored event on the explorer with the same hash. Only if this is configured. |
| 4:40 | Today | Close on the one line above. | |

## If something goes wrong on camera

Click Reset demo in the simulator. It reseeds in about two seconds. The demo never needs the internet or a language model in fixture mode.

## Checklist for the upload

Keep the Synthetic demo data line and the Demo bank label visible. Do not state any real customer, saving or accuracy. After upload, add the video title and link to the README.
