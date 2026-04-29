.PHONY: e2e-clean e2e-clean-remote e2e e2e-up e2e-down

e2e-clean:
	@echo "Destroying any local labs matching ncli-e2e-*"
	@containerlab inspect --all --format json 2>/dev/null \
	  | python -c "import json,sys; [print(l['lab_name']) for l in json.load(sys.stdin).get('containers',[]) if l.get('lab_name','').startswith('ncli-e2e-')]" \
	  | sort -u \
	  | xargs -I{} containerlab destroy --name {} --cleanup

e2e-clean-remote:
	@if [ -z "$(HOST)" ]; then echo "Usage: make e2e-clean-remote HOST=<host>" >&2; exit 1; fi
	@ssh $(HOST) 'containerlab inspect --all --format json | python3 -c "import json,sys; [print(l[\"lab_name\"]) for l in json.load(sys.stdin).get(\"containers\",[]) if l.get(\"lab_name\",\"\").startswith(\"ncli-e2e-\")]" | sort -u | xargs -I{} containerlab destroy --name {} --cleanup'

e2e:
	pytest -m clab -v

e2e-up:
	@python scripts/e2e_up.py $(if $(HOST),--host $(HOST))

e2e-down:
	@if [ ! -f tests/e2e/_scratch/lab.txt ]; then echo "no scratch lab found"; exit 0; fi
	@LAB=$$(head -1 tests/e2e/_scratch/lab.txt); \
	 YML=$$(sed -n 2p tests/e2e/_scratch/lab.txt); \
	 echo "Destroying $$LAB"; \
	 if [ -n "$(HOST)" ]; then \
	   ssh $(HOST) "containerlab destroy -t $$YML --cleanup"; \
	 else \
	   containerlab destroy -t "$$YML" --cleanup; \
	 fi; \
	 rm -f tests/e2e/_scratch/lab.txt tests/e2e/_scratch/inventory.yaml
