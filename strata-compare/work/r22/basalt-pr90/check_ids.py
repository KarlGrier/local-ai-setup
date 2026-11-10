"""check_ids.py TREE DATA_DIR GGUF_SHARD_1 - do Basalt's bench ids (data/bench/*.ids at b2fe96bf30, extracted as plain
data) decode to the same text with OUR tokenizer and chat template, and does our template re-encode to the same ids?
conv / struct / prose: the whole chat-templated prompt (thinking off, generation prompt added); prefill: before / body /
after around a marker. Read-only; nothing from Basalt is imported or run."""
import sys
from pathlib import Path

tree, data, gguf = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(tree))
sys.path.insert(0, str(tree / "tools"))
from strata_tokenizer import Tokenizer          # noqa: E402
from serve.frontend import ChatTemplate          # noqa: E402

t = Tokenizer.from_gguf(gguf)
c = ChatTemplate(str(tree / "serve" / "chat_template.jinja"))
render = lambda msgs: c.render(msgs, enable_thinking=False)     # noqa: E731
ids_of = lambda name: [[int(x) for x in l.split(",")] for l in (data / name).read_text().strip().split("\n")]   # noqa: E731
MARK = "⁣BODY⁣"
probe = render([{"role": "user", "content": MARK}])
pre_txt, post_txt = probe.split(MARK)
print(f"tree {tree.name}: template prefix {pre_txt!r} / suffix {post_txt!r}")
for name in ("conv", "struct", "prose"):
    ids = ids_of(f"{name}.ids")[0]
    text = t.decode(ids)
    if not (text.startswith(pre_txt) and text.endswith(post_txt)):
        print(f"  {name}: MISMATCH - the decoded text is not our template around one user message: {text[:120]!r} ... {text[-80:]!r}")
        continue
    user = text[len(pre_txt):len(text) - len(post_txt)]
    ours = t.encode(render([{"role": "user", "content": user}]), parse_special=True)
    same = ours == ids
    diff = next((i for i, (a, b) in enumerate(zip(ours, ids)) if a != b), None)
    print(f"  {name}: {len(ids)} ids, user text {len(user)} chars {user[:70]!r}...; re-encoded with our template: "
          f"{'IDENTICAL' if same else f'DIFFERENT ({len(ours)} vs {len(ids)} ids, first difference at {diff})'}")
pre, body, post = ids_of("prefill.ids")
pre_d, post_d = t.decode(pre), t.decode(post)
head = pre_d[len(pre_txt):] if pre_d.startswith(pre_txt) else None
print(f"  prefill: before {len(pre)} ids -> {pre_d!r} ({'starts with our prefix; user text begins ' + repr(head) if head is not None else 'DOES NOT start with our prefix ' + repr(pre_txt)})")
body_txt = t.decode(body)
tail = post_d[:len(post_d) - len(post_txt)] if post_d.endswith(post_txt) else None
print(f"  prefill: after {len(post)} ids -> {post_d!r} ({'ends with our suffix; question ' + repr(tail) if tail is not None else 'DOES NOT end with our suffix ' + repr(post_txt)})")
whole_ids = pre + body + post
user = (head or "") + body_txt + (tail or "")
ours = t.encode(render([{"role": "user", "content": user}]), parse_special=True)
diff = next((i for i, (a, b) in enumerate(zip(ours, whole_ids)) if a != b), None)
print(f"  prefill: body {len(body)} ids, {len(body_txt)} chars; the whole 16K prompt re-encoded with our template: "
      f"{'IDENTICAL' if ours == whole_ids else f'DIFFERENT ({len(ours)} vs {len(whole_ids)} ids, first difference at {diff})'}")
