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

Replace the placeholders truthfully before submission; the course rubric requires each group member's actual contribution.

| Task / Feature | Member 1 | Member 2 | Member 3 | Member 4 |
|---|---|---|---|---|
| TCP, framing, dispatch | TBD | TBD | TBD | TBD |
| Lifecycle and mulligan | TBD | TBD | TBD | TBD |
| Turn, priority, stack, combat | TBD | TBD | TBD | TBD |
| Client, testing, documentation | TBD | TBD | TBD | TBD |

## AI Usage
