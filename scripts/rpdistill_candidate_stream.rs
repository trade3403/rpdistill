//! CI-only bridge against pinned upstream rpmodel. Not a production package loader.
use rpmodel::{package, safetensors::{Dtype, SafeTensorReader}};
use std::{fs::File, io::{self, BufWriter, Write}};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path=std::env::args().nth(1).ok_or("missing weight file")?;
    let file=File::open(path)?;
    if file.metadata()?.len()>400*1024*1024 {
        return Err("weight file exceeds budget".into());
    }
    let mut reader=SafeTensorReader::open(file).map_err(|e|format!("{e:?}"))?;
    if reader.metadata().get("rpdistill_format").map(String::as_str)!=Some("1")
        || reader.metadata().contains_key("rpmodel_format") {
        return Err("wrong independent candidate format".into());
    }
    let shapes=package::expected_shapes();
    let entries:Vec<_>=reader.tensors().iter().map(|(n,i)|(n.clone(),i.clone())).collect();
    if entries.len()!=256 || entries.len()!=shapes.len() {
        return Err("wrong tensor inventory".into());
    }
    let mut out=BufWriter::with_capacity(64*1024,io::stdout().lock());
    for (name,info) in entries {
        if info.dtype!=Dtype::F32 || shapes.get(&name)!=Some(&info.shape) {
            return Err("wrong tensor shape or dtype".into());
        }
        let mut start=0;
        while start<info.elements {
            let count=(info.elements-start).min(1024*1024) as usize;
            let values=reader.read_f32(&name,start,count).map_err(|e|format!("{e:?}"))?;
            for value in values {
                if !value.is_finite() { return Err("nonfinite weight".into()); }
                out.write_all(&value.to_le_bytes())?;
            }
            start+=count as u64;
        }
    }
    out.flush()?;
    Ok(())
}
