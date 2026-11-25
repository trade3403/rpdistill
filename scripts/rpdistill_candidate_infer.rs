//! Independent diagnostic bridge. Never bypass the official model loader.
use rpmodel::{config::MarianConfig, package, safetensors::{Dtype,SafeTensorReader},sha256::digest_reader};
use rpinfer::{marian_decoder::{MarianDecoder,DECODER_PAYLOAD_BYTES},
    marian_encoder::{MarianEncoder,ENCODER_PAYLOAD_BYTES},
    marian_weights::MarianEmbeddings,marian_generation::MarianEncoded,
    matmul::Kernel,search::SearchConfig,tensor::Tensor};
use std::{fs::{self,File},io::{self,BufWriter,Seek,SeekFrom,Write},path::Path};

fn valid_id(s:&str)->bool {
    s.len()==64 && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn write_tensor(out:&mut impl Write,t:&Tensor)->io::Result<()> {
    for &v in t.data() { out.write_all(&v.to_le_bytes())?; }
    Ok(())
}
fn main()->Result<(),Box<dyn std::error::Error>> {
    let args:Vec<String>=std::env::args().collect();
    if args.len()!=4 || !valid_id(&args[2]) || !valid_id(&args[3]) {
        return Err("usage: bridge ROOT EXPECTED_WEIGHTS_SHA256 EXPECTED_CHECKPOINT_ID".into());
    }
    let root=Path::new(&args[1]);
    if !fs::symlink_metadata(root)?.file_type().is_dir() {return Err("invalid root".into());}
    // Package identity and manifest are checked by the Python caller. The
    // bridge independently verifies weight bytes and pinned asset bytes.
    let model=package::verified_asset(root,"config.json").map_err(|e|format!("{e:?}"))?;
    let generation=package::verified_asset(root,"generation_config.json").map_err(|e|format!("{e:?}"))?;
    for name in ["source.spm","target.spm","vocab.json"] {
        package::verified_asset(root,name).map_err(|e|format!("{e:?}"))?;
    }
    let config=MarianConfig::parse(std::str::from_utf8(&model)?,std::str::from_utf8(&generation)?)
        .map_err(|e|format!("{e:?}"))?;
    let path=root.join("weights.safetensors");
    if !fs::symlink_metadata(&path)?.file_type().is_file() {return Err("invalid weights file".into());}
    let mut file=File::open(path)?;
    let size=file.metadata()?.len();
    if !(package::PAYLOAD_BYTES..=package::PAYLOAD_BYTES+8*1024*1024+8).contains(&size) {
        return Err("weight file exceeds fixed profile".into());
    }
    let (actual,hash)=digest_reader(&mut file,size)?;
    if actual!=size || hash!=args[2] {return Err("weight pin mismatch".into());}
    file.seek(SeekFrom::Start(0))?;
    let mut reader=SafeTensorReader::open(file).map_err(|e|format!("{e:?}"))?;
    let meta=reader.metadata();
    if meta.len()!=3 || meta.get("format").map(String::as_str)!=Some("pt")
        || meta.get("rpdistill_format").map(String::as_str)!=Some("1")
        || meta.get("source_checkpoint_id").map(String::as_str)!=Some(args[3].as_str()) {
        return Err("candidate metadata mismatch".into());
    }
    let shapes=package::expected_shapes();
    if shapes.len()!=256 || reader.tensors().len()!=shapes.len() {
        return Err("unexpected tensor inventory".into());
    }
    for (name,shape) in &shapes {
        let t=reader.tensors().get(name).ok_or("missing tensor")?;
        if t.dtype!=Dtype::F32 || &t.shape!=shape {return Err("tensor mismatch".into());}
    }
    let embeddings=MarianEmbeddings::load(&mut reader,&config,135_479_204).map_err(|e|format!("{e:?}"))?;
    let encoder=MarianEncoder::load(&mut reader,&config,ENCODER_PAYLOAD_BYTES).map_err(|e|format!("{e:?}"))?;
    let decoder=MarianDecoder::load(&mut reader,&config,DECODER_PAYLOAD_BYTES).map_err(|e|format!("{e:?}"))?;
    drop(reader);
    let cases:[(&[u32],&[bool],&[u32],&[bool]);2]=[
        (&[2,3,0],&[true,true,true],&[65000,4],&[true,true]),
        (&[2047,2048,0,65000],&[true,true,true,false],&[65000,17,65000,4],&[true,true,false,true])
    ];
    let mut out=BufWriter::with_capacity(64*1024,io::stdout().lock());
    for (source,source_mask,target,target_mask) in cases {
        let memory=encoder.forward(&embeddings,source,Some(source_mask),Kernel::Auto).map_err(|e|format!("{e:?}"))?;
        let encoded=MarianEncoded::new(&decoder,&embeddings,&memory,Some(source_mask),Kernel::Auto)
            .map_err(|e|format!("{e:?}"))?;
        let full=encoded.logits(target,Some(target_mask),false).map_err(|e|format!("{e:?}"))?;
        let cached=encoded.cached_logits(target,Some(target_mask)).map_err(|e|format!("{e:?}"))?;
        write_tensor(&mut out,&memory)?;
        write_tensor(&mut out,&full)?;
        write_tensor(&mut out,&cached)?;
        let search=SearchConfig{start:config.generation.start,eos:config.generation.eos,
            beam_width:1,min_new:0,max_new:3,length_penalty:1.0,
            suppress:&config.generation.suppress,force_eos_at_limit:false};
        let a=encoded.generate(search).map_err(|e|format!("{e:?}"))?;
        let b=encoded.generate_cached(search).map_err(|e|format!("{e:?}"))?;
        if a.len()!=1 || b.len()!=1 || a[0].tokens!=b[0].tokens || a[0].ended!=b[0].ended {
            return Err("full and cached generation differ".into());
        }
        let ids=&a[0].tokens;
        out.write_all(&(ids.len() as u32).to_le_bytes())?;
        for id in ids {out.write_all(&id.to_le_bytes())?;}
    }
    out.flush()?;
    Ok(())
}
