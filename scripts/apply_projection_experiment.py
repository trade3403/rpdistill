"""Apply a bounded row-parallel FP32 output-head experiment to a disposable D checkout.

Never run on the user's production tree. The pinned reference is deliberately
unchanged in its own repository. All per-cell accumulation order is preserved.
"""
from pathlib import Path
import subprocess
import sys

REFERENCE="2fa70c175de7a25415489ecb12ffe3d09485f777"
OLD_TRAIT="pub trait RowTable: private::Sealed {"
NEW_TRAIT="pub trait RowTable: private::Sealed + Sync {"
OLD_LOOP="""        let mut data = buffer(size)?;
        for row in hidden.data()[start..].chunks_exact(width) {
            for id in 0..vocab {
                let w = weight.row(id)?;
                let mut sum = 0.0_f32;
                for (&x, &y) in row.iter().zip(w) {
                    sum += x * y;
                }
                if let Some(bias) = self.bias {
                    sum += bias.data()[id];
                }
                data.push(sum);
            }
        }
"""
NEW_LOOP="""        let mut data = buffer(size)?;
        data.resize(size, 0.0);
        let bias = self.bias;
        // Independent vocabulary rows; preserve ascending feature accumulation.
        let workers = std::thread::available_parallelism()
            .map(|n| n.get()).unwrap_or(1).min(4);
        for (row, output) in hidden.data()[start..].chunks_exact(width)
            .zip(data.chunks_exact_mut(vocab)) {
            let project = |first: usize, cells: &mut [f32]| -> Result<(), Error> {
                for (offset, cell) in cells.iter_mut().enumerate() {
                    let id = first + offset;
                    let w = weight.row(id)?;
                    let mut sum = 0.0_f32;
                    for (&x, &y) in row.iter().zip(w) {
                        sum += x * y;
                    }
                    if let Some(bias) = bias {
                        sum += bias.data()[id];
                    }
                    *cell = sum;
                }
                Ok(())
            };
            if workers == 1 || vocab * width < 1_048_576 {
                project(0, output)?;
            } else {
                let stride = vocab.div_ceil(workers);
                std::thread::scope(|scope| -> Result<(), Error> {
                    let mut handles = Vec::new();
                    for (index, cells) in output.chunks_mut(stride).enumerate() {
                        let project = &project;
                        let handle = std::thread::Builder::new()
                            .spawn_scoped(scope, move || project(index * stride, cells))
                            .map_err(|_| Error::Worker)?;
                        handles.push(handle);
                    }
                    for handle in handles {
                        handle.join().map_err(|_| Error::Worker)??;
                    }
                    Ok(())
                })?;
            }
        }
"""


def replace_exact(text,old,new):
    if text.count(old)!=1:
        raise ValueError("pinned source anchor mismatch")
    return text.replace(old,new,1)


def apply(root):
    root=Path(root).resolve(strict=True)
    head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if head!=REFERENCE:
        raise ValueError("unexpected D revision")
    relative=["rptranslate/crates/rpinfer/src/vocabulary.rs",
              "rptranslate/crates/rpinfer/src/seq2seq.rs"]
    subprocess.run(["git","-C",str(root),"diff","--quiet","HEAD","--",*relative],check=True)
    paths=[root/name for name in relative]
    values=[replace_exact(paths[0].read_text(encoding="utf-8"),OLD_TRAIT,NEW_TRAIT),
            replace_exact(paths[1].read_text(encoding="utf-8"),OLD_LOOP,NEW_LOOP)]
    for path,value in zip(paths,values):
        path.write_text(value,encoding="utf-8")


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: apply_projection_experiment.py DISPOSABLE_D_CHECKOUT")
    apply(sys.argv[1])
