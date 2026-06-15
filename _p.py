import pathlib
p=pathlib.Path("app/services/pipeline.py")
s=p.read_text()
k="create_task(self._execute"
c="        await db.commit()"+chr(10)
d=False
o=[]
for ln in s.splitlines(True):
 if k in ln and not d:
  o.append(c)
  d=True
 o.append(ln)
p.write_text("".join(o))
print("patched",d)
