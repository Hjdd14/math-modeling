## Summary

- 

## Checks

- [ ] I updated tests or explained why tests are not needed.
- [ ] I updated `SKILL.md` or `references/` if the workflow changed.
- [ ] I did not weaken the parallel Agent phase gates.
- [ ] I ran the relevant verification commands.

## Verification

```powershell
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
```

## Notes

- 
