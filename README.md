# MTGNP v1.0 Client-Server Project

Two-player, server-authoritative Magic: The Gathering teaching implementation using TCP port 4444 and the CSNETWK MTGNP v1.0 protocol.

## Requirements and setup

- Python 3.10 or newer
- `openpyxl` only when rebuilding `card_instances.json`

```bash
python -m pip install openpyxl
python build_catalog.py
python server.py --verbose
python client.py --verbose
```

Both clients choose distinct, non-empty player IDs. The supplied client takes the first 50 distinct catalog instances as its demonstration deck. The server is authoritative: clients render `GAME_STATE_UPDATE` and submit actions using the sequence number issued by the server.

Run automated checks with `python -m unittest -v test_mtgnp.py`.

## Implemented protocol behavior

- Four-byte big-endian framing, exact reads, UTF-8 JSON, and the 65,535-byte cap
- Exactly two simultaneous clients, PING/PONG, disconnect grace period, and state-preserving reconnection
- Lobby, validated decks, setup, randomized starting player, London mulligan, restart on the same connections
- Full turn sequence including combat substeps, cleanup discard, land limit, turn-one draw rule, and empty-library/life/concession losses
- Personalized hidden hands and authoritative zones, life totals, stack, and turn state
- Priority tokens, stale-action rejection, LIFO stack, mana payment, land tapping, spell casting and resolution
- Combat declarations, summoning sickness, multiple blockers and ordering, simultaneous damage, deaths, and result broadcasts
- Explicit recognition of all 25 PDU types; trigger/activated-ability requests are rejected cleanly when no supported ability is pending
- Interactive client commands for lands, spells, attackers, blockers, damage ordering, passing and conceding
- Client inputs are validated and reprompted (IDs, menus, lists, combat pairs, trigger choices, and ports); server PDU fields are independently type/shape checked and rejected with `ERROR` without changing game state

## Implemented card effects

Lightning Bolt, Shock, Lava Spike, Flame Slash, Searing Spear, Giant Growth and Counterspell have explicit spell-resolution logic. The implemented trigger subset covers Monastery Swiftspear, Goblin Guide, Phantasmal Bear, Gray Merchant and Gravedigger. Tap abilities are supported for Llanowar Elves, Elvish Mystic, Sol Ring, Merfolk Looter, Prodigal Sorcerer, Royal Assassin, Millstone and Rod of Ruin. Creature spells also resolve to the battlefield. Other catalog cards use generic permanent or graveyard behavior where applicable; their bespoke rules text is not fully implemented.

## Known limitations / RFC deviations

- The implementation is a rubric-oriented simplified engine, not the complete Magic Comprehensive Rules.
- First strike is implemented. The trigger framework supports Prowess, Goblin Guide, Phantasmal Bear, Gray Merchant, and Gravedigger, including ordering and target-choice PDUs. Selected tap abilities are implemented. Replacement effects, protection, regeneration, trample, variable costs, and most other bespoke catalog effects are not implemented.
- Mana payment automatically taps suitable basic lands; there is no separate mana-pool selection UI.
- Reconnection is supported by resending `PLAYER_READY` with the exact same ID and deck within 30 seconds. The bundled interactive client does not automatically reconnect after its socket closes.
- Trigger ordering and target choices are supported for the implemented trigger subset; optional "you may" effects outside that subset remain unsupported.

## Work Distribution Matrix

Legend:
- ✅: full contribution
- 🟰: partial contribution
- ❌: no contribution

| Task / Feature | Ileto, Miguel | Lee, Maria Isabella | Varela, Maxine | Yana, Jeon |
|---|---|---|---|---|
| TCP Server: connection handling, framing, dispatch | 🟰 | ❌ | ✅ | 🟰 |
| Game lifecycle: LOBBY, GAME_SETUP, MULLIGAN logic | ❌ | ✅ | 🟰 | ✅ |
| Turn & phase engine (all phases/steps, transitions) | ❌ | 🟰 | ✅ | ✅ |
| Priority & Stack logic, spell/ability resolution | ❌ | 🟰 | ✅ | 🟰 |
| Combat system (attackers, blockers, damage) | ❌ | 🟰 | 🟰 | 🟰 |
| Client implementation & state rendering | ❌ | ✅ | 🟰 | ✅ |
| PDU serialisation/deserialisation (all 25 PDU types) | ❌ | 🟰 | 🟰 | 🟰 |
| Error handling, PING/PONG heartbeat, disconnect logic | ❌ | 🟰 | ✅ | 🟰 |
| Verbose mode (client + server PDU logging, toggle on/off) | ❌ | ✅ | 🟰 | ❌ |
| Testing & interoperability | ❌ | ✅ | ❌ | ✅ |
| README / documentation / AI disclosure | ❌ | ✅ | ✅ | ✅ |

## AI Usage

The following were used:
* ChatGPT:
  * To understand each part of specs
  * Asked help to generate code
* Claude:
  * To understand each part of specs
  * Asked help to generate code
  * Asked help to check whether code meets specs
* Gemini:
  * To understand each part of specs
  * Asked help to generate code
  * Asked help to check whether code meets specs
  * To help understand some parts of the code
