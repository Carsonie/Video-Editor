# Basic_E2E_Testing — terminal entry points
#
# Run `make` on its own to see what is here.
#
# ⚠ This is NOT Rentify_v10's Makefile. That repo has its own (`make
# copy-storage`, `make replace-storage`); nothing here reaches into it.

SHELL   := /bin/bash
EDITOR  := layers.sh
STORE   ?= Rentify Demos Corp/ski-demo
# A store has SEVERAL videos — six E2E tests, and more than one deserves its own
# help video. Each lives under help-videos/videos/<NN-slug>/ with its own dev/,
# sandbox/, script and outputs. Only raw_mp4/ is shared, because a recording is
# already named for the scenario it captured.
#
# paths.py takes the ROOT as a parameter and never hardcodes a folder name, so
# adding this dimension was a move plus this variable — not a rewrite.
VIDEO   ?= 01-first-time-ordering
FINAL   := $(if $(filter .,$(VIDEO)),Customers/$(STORE)/help-videos/final,Customers/$(STORE)/help-videos/videos/$(VIDEO))
# Paths come from the resolver, never from a directory listing: a scene's files
# live in dev/<NN>-<label>/ now, a store may be half-migrated, and a sandbox
# edit outranks both. Only paths.py knows all three.
OP      := build/onepass_narration.py
PY      := python3 -c "import sys;sys.path.insert(0,'shared');import paths;exec(sys.argv[1])"

.DEFAULT_GOAL := help
.PHONY: help editor editor-stop layers scenes overlays vtt videos sandbox-sync \
        onepass-script onepass-render onepass-split

help:
	@echo ""
	@echo "  make editor            open the frame editor (Browse — pick files by hand)"
	@echo "  make layers BASE=… OVERLAY=…"
	@echo "                         open a LAYERED view: mp4 underneath, alpha WebM on top"
	@echo "  make scenes            layered view on scene 1 of the current cut, with the"
	@echo "                         scene list beside it — the usual starting point"
	@echo "  make editor-stop       stop the editor server"
	@echo "  make overlays          rebuild the per-scene avatar clips (a new scenes v#)"
	@echo "                         run this after any narration re-render"
	@echo "  make vtt               print the Video Timing Table for the current store"
	@echo ""
	@echo "  make onepass-script    compose the whole script with breaks + show the cost (free)"
	@echo "  make onepass-render    ONE HeyGen render of the whole script  (COSTS MONEY)"
	@echo "  make onepass-split     cut it back into per-scene narration    (free)"
	@echo ""
	@echo "  make build             build EVERY scene alone and check it —"
	@echo "                         frames, clock, audio. DO THIS FIRST."
	@echo "  make join V=28         join them (refuses while a scene fails)"
	@echo "  make release V=28      hand v28 to Basic_E2E_Testing"
	@echo "  make trim              trim z_History to the 3 newest"
	@echo ""
	@echo "  make sandbox-sync      refill sandbox/ from dev/ (the undo)"
	@echo "  make videos            list this store's videos"
	@echo ""
	@echo "  STORE defaults to \"$(STORE)\""
	@echo "  VIDEO defaults to \"$(VIDEO)\""
	@echo "    make scenes VIDEO=\"02-booking-for-your-party\""
	@echo "    make vtt STORE=\"Rentify Demos Corp/canoe-demo\" VIDEO=."
	@echo ""

# Browse, then pick ▩ background and ◈ overlay by hand.
editor:
	@"$(EDITOR)"

editor-stop:
	@"$(EDITOR)" --stop

# Explicit pair. Paths may be absolute, repo-relative, or relative to Customers/.
#   make layers BASE=".../Num_5-v6-segment.mp4" OVERLAY=".../sarah-closeout-alpha.webm"
layers:
	@if [ -z "$(BASE)" ] || [ -z "$(OVERLAY)" ]; then \
	  echo "  ✗ needs BASE and OVERLAY, e.g."; \
	  echo "      make layers BASE=\"$(STORE)/help-videos/final/segments/Num_1-v6-segment.mp4\" \\"; \
	  echo "                  OVERLAY=\"$(STORE)/help-videos/final/sarah_clips/sarah-closeout-alpha.webm\""; \
	  exit 1; \
	fi
	@"$(EDITOR)" "$(BASE)" "$(OVERLAY)"

# The common case: scene 1 of the newest cut, with the avatar laid over it and
# every other scene one click away in the panel. The version is discovered
# rather than hardcoded, so this keeps working after the next re-cut.
scenes:
	@set -euo pipefail; \
	v=$$($(PY) "x=paths.versions('$(FINAL)')['segment'];print(x[0] if x else '')"); \
	if [ -z "$$v" ]; then echo "  x no segments found for $(STORE)"; exit 1; fi; \
	base=$$($(PY) "print(paths.sandbox_only('$(FINAL)',1)['segment'] or '')"); \
	ov=$$($(PY) "print(paths.sandbox_only('$(FINAL)',1)['avatar'] or '')"); \
	if [ -z "$$base" ]; then echo "  x scene 1 has no sandbox copy. Run: make sandbox-sync"; exit 1; fi; \
	ovv=$$($(PY) "x=paths.versions('$(FINAL)')['avatar'];print(x[0] if x else '')"); \
	scr=$$(ls "$(FINAL)/video"/script_v*.json 2>/dev/null | sed -n 's/.*script_v\([0-9]*\)\.json/\1/p' | sort -n | tail -1); \
	lay=$$($(PY) "print(paths.layout('$(FINAL)'))"); \
	echo "  layout:         $$lay"; \
	echo "  newest segment: v$$v"; \
	if [ -n "$$ovv" ]; then echo "  newest scenes:  v$$ovv   (per-scene avatar + audio)"; \
	else echo "  newest scenes:  none - run 'make overlays' or every scene shares one clip"; fi; \
	if [ -n "$$scr" ]; then echo "  newest script:  v$$scr"; fi; \
	if [ -z "$$ov" ] || [ ! -f "$$ov" ]; then \
	  ov=$$(ls "$(FINAL)/sarah_clips"/sarah-closeout-alpha.webm 2>/dev/null | head -1); \
	fi; \
	sb=$$($(PY) "import os;r=paths.sandbox_root('$(FINAL)');print(sum(1 for d in (os.listdir(r) if os.path.isdir(r) else []) if os.path.isdir(os.path.join(r,d)) and any(f.startswith(('segment','narration','avatar')) for f in os.listdir(os.path.join(r,d)))))"); \
	echo "  editor scope:   sandbox  (dev/ is the safe copy, never touched)"; \
	if [ "$$sb" != "0" ]; then echo "  sandbox copies: $$sb scene(s)"; fi; \
	if [ -z "$$ov" ]; then echo "  x no avatar clip found under $(FINAL)/sarah_clips"; exit 1; fi; \
	"$(EDITOR)" "$$base" "$$ov"

# Which videos does this store have? A store that has not been restructured yet
# has none — its work sits in help-videos/final/, and VIDEO=. reaches it.
videos:
	@d="Customers/$(STORE)/help-videos/videos"; \
	if [ -d "$$d" ]; then \
	  echo ""; for v in "$$d"/*/; do \
	    [ -d "$$v" ] || continue; \
	    n=$$(basename "$$v"); \
	    sc=$$($(PY) "print(len(paths.scenes_from_script('$$v')))" 2>/dev/null || echo "?"); \
	    printf "  %-34s %s scenes\n" "$$n" "$$sc"; \
	  done; echo ""; \
	else \
	  echo "  no videos/ folder — this store is still flat. Use VIDEO=. to reach help-videos/final/"; \
	fi

# Refill sandbox/ from dev/. The editor reads and writes sandbox ONLY, so this
# is how a scene gets back to the known-good copy — per scene, or all of them.
# It OVERWRITES: that is the point, it is the undo.
sandbox-sync:
	@$(PY) "import os,shutil;R='$(FINAL)';c=0;\
	[[(shutil.copy2(s,os.path.join(paths.sandbox_dir(R,n,l),o)),globals().__setitem__('c',0)) \
	  for rx,o in ((paths.DEV_SEG_RE,'segment.mp4'),(paths.DEV_NAR_RE,'narration.webm'),(paths.DEV_AV_RE,'avatar.webm')) \
	  for s in [paths._newest(paths.scene_dir(R,n,l),rx)[0]] if s and os.makedirs(paths.sandbox_dir(R,n,l),exist_ok=True) is None] \
	 for n,l in paths.scenes_from_script(R)];print('  sandbox refilled from dev/')"

# One corner-composited avatar clip per scene, versioned. Without a set of these
# the editor lays ONE clip over every scene, so scene 5's footage plays scene
# 12's voice — the picture changes as you click and the audio never does.
overlays:
	@python3 build/make_scene_overlays.py "$(FINAL)"

vtt:
	@python3 shared/vtt.py "$(FINAL)"

# ONE HeyGen render for the whole script, split back into per-scene clips.
# Rendering scene by scene gives Sarah no run-up into a sentence and no run-out
# of one, so every join is a small jolt — and there are eleven of them.
#
# `onepass-script` and `onepass-split` are FREE. `onepass-render` is the only
# one that spends money, which is why it is a separate target rather than a
# step inside another one.
onepass-script:
	@python3 $(OP) script "$(FINAL)" $(if $(BRK),--brk $(BRK),)

onepass-render:
	@python3 $(OP) render "$(FINAL)" $(if $(BRK),--brk $(BRK),)

onepass-split:
	@python3 $(OP) split "$(FINAL)" $(if $(MINGAP),--min-gap $(MINGAP),) $(if $(DRY),--dry-run,)

# ── building ──────────────────────────────────────────────────────────────
# SCENES FIRST, ALWAYS. `join` will not run while a scene fails its checks.
# Four whole-video builds shipped faults one scene would have shown in seconds.
.PHONY: build join release trim
build:
	@python3 build/build_scenes.py "$(FINAL)"

join:
	@if [ -z "$(V)" ]; then echo "  which version?   make join V=28"; exit 1; fi
	@python3 build/build_scenes.py "$(FINAL)" --join $(V)

release:
	@if [ -z "$(V)" ]; then echo "  which version?   make release V=28"; exit 1; fi
	@python3 build/release_video.py "$(FINAL)" --version $(V)

trim:
	@python3 build/trim_history.py Customers
