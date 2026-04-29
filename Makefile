.PHONY: e2e-clean e2e-clean-remote

e2e-clean:
	@echo "Destroying any local labs matching ncli-e2e-*"
	@containerlab inspect --all --format json 2>/dev/null \
	  | python -c "import json,sys; [print(l['lab_name']) for l in json.load(sys.stdin).get('containers',[]) if l.get('lab_name','').startswith('ncli-e2e-')]" \
	  | sort -u \
	  | xargs -I{} containerlab destroy --name {} --cleanup

e2e-clean-remote:
	@if [ -z "$(HOST)" ]; then echo "Usage: make e2e-clean-remote HOST=<host>" >&2; exit 1; fi
	@ssh $(HOST) 'containerlab inspect --all --format json | python3 -c "import json,sys; [print(l[\"lab_name\"]) for l in json.load(sys.stdin).get(\"containers\",[]) if l.get(\"lab_name\",\"\").startswith(\"ncli-e2e-\")]" | sort -u | xargs -I{} containerlab destroy --name {} --cleanup'
