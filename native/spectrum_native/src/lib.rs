use flate2::read::ZlibDecoder;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::io::Read;

const HEADER_SIZE: usize = 16;
const MAGIC: &[u8; 4] = b"SPEC";

enum LastPiece {
    None,
    Token { offset: usize, len: usize },
    Extension { offset: usize, len: usize },
    Inline(Vec<u8>),
}

fn read_u32_le(data: &[u8], offset: usize) -> PyResult<u32> {
    let bytes = data
        .get(offset..offset + 4)
        .ok_or_else(|| PyValueError::new_err("Truncated uint32 table"))?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

fn token_piece<'a>(
    token_id: u32,
    token_blob: &'a [u8],
    token_offsets: &[u8],
    token_lengths: &[u8],
) -> PyResult<Option<&'a [u8]>> {
    let table_offset = token_id as usize * 4;
    if table_offset + 4 > token_offsets.len() || table_offset + 4 > token_lengths.len() {
        return Ok(None);
    }
    let len_raw = read_u32_le(token_lengths, table_offset)?;
    if len_raw == u32::MAX {
        return Ok(None);
    }
    let len = len_raw as usize;
    let offset = read_u32_le(token_offsets, table_offset)? as usize;
    let piece = token_blob
        .get(offset..offset + len)
        .ok_or_else(|| PyValueError::new_err("Token byte table points past EOF"))?;
    Ok(Some(piece))
}

fn extension_piece<'a>(
    token_id: u32,
    extension_ids: &[u8],
    extension_blob: &'a [u8],
    extension_offsets: &[u8],
    extension_lengths: &[u8],
) -> PyResult<Option<&'a [u8]>> {
    let count = extension_ids.len() / 4;
    let mut lo = 0usize;
    let mut hi = count;
    while lo < hi {
        let mid = (lo + hi) / 2;
        let candidate = read_u32_le(extension_ids, mid * 4)?;
        if candidate < token_id {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    if lo >= count || read_u32_le(extension_ids, lo * 4)? != token_id {
        return Ok(None);
    }

    let offset = read_u32_le(extension_offsets, lo * 4)? as usize;
    let len = read_u32_le(extension_lengths, lo * 4)? as usize;
    let piece = extension_blob
        .get(offset..offset + len)
        .ok_or_else(|| PyValueError::new_err("Extension byte table points past EOF"))?;
    Ok(Some(piece))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn decode_code_spec_bytes_fast(
    data: &[u8],
    token_blob: &[u8],
    token_offsets: &[u8],
    token_lengths: &[u8],
    extension_ids: &[u8],
    extension_blob: &[u8],
    extension_offsets: &[u8],
    extension_lengths: &[u8],
    spec_id_rle: u32,
    spec_id_unicode: u32,
) -> PyResult<String> {
    if data.len() < HEADER_SIZE {
        return Err(PyValueError::new_err("File too short to contain a valid header"));
    }
    if &data[0..4] != MAGIC {
        return Err(PyValueError::new_err("Bad SPEC magic bytes"));
    }

    let orig_length = u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize;
    let mut decoder = ZlibDecoder::new(&data[HEADER_SIZE..]);
    let mut raw_stream = Vec::new();
    decoder
        .read_to_end(&mut raw_stream)
        .map_err(|err| PyValueError::new_err(format!("zlib decompression failed: {err}")))?;
    if raw_stream.len() % 4 != 0 {
        return Err(PyValueError::new_err("Token ID stream is not uint32-aligned"));
    }

    let mut out = Vec::with_capacity(orig_length);
    let mut pending_unicode = false;
    let mut pending_rle = false;
    let mut last_piece = LastPiece::None;

    for chunk in raw_stream.chunks_exact(4) {
        let val = u32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]);

        if pending_unicode {
            let ch = char::from_u32(val)
                .ok_or_else(|| PyValueError::new_err(format!("Invalid Unicode code point {val}")))?;
            let mut buf = [0u8; 4];
            let encoded = ch.encode_utf8(&mut buf).as_bytes();
            out.extend_from_slice(encoded);
            last_piece = LastPiece::Inline(encoded.to_vec());
            pending_unicode = false;
            continue;
        }

        if pending_rle {
            if val > 0 {
                match &last_piece {
                    LastPiece::None => {}
                    LastPiece::Token { offset, len } => {
                        let piece = &token_blob[*offset..*offset + *len];
                        for _ in 0..val {
                            out.extend_from_slice(piece);
                        }
                    }
                    LastPiece::Extension { offset, len } => {
                        let piece = &extension_blob[*offset..*offset + *len];
                        for _ in 0..val {
                            out.extend_from_slice(piece);
                        }
                    }
                    LastPiece::Inline(piece) => {
                        for _ in 0..val {
                            out.extend_from_slice(piece);
                        }
                    }
                }
            }
            pending_rle = false;
            continue;
        }

        if val == spec_id_unicode {
            pending_unicode = true;
            continue;
        }
        if val == spec_id_rle {
            pending_rle = true;
            continue;
        }

        if let Some(piece) = token_piece(val, token_blob, token_offsets, token_lengths)? {
            out.extend_from_slice(piece);
            let offset = piece.as_ptr() as usize - token_blob.as_ptr() as usize;
            last_piece = LastPiece::Token {
                offset,
                len: piece.len(),
            };
            continue;
        }

        if let Some(piece) = extension_piece(
            val,
            extension_ids,
            extension_blob,
            extension_offsets,
            extension_lengths,
        )? {
            out.extend_from_slice(piece);
            let offset = piece.as_ptr() as usize - extension_blob.as_ptr() as usize;
            last_piece = LastPiece::Extension {
                offset,
                len: piece.len(),
            };
            continue;
        }

        return Err(PyValueError::new_err(format!("Unknown token ID {val}")));
    }

    if out.len() > orig_length {
        out.truncate(orig_length);
    }
    Ok(String::from_utf8_lossy(&out).into_owned())
}

#[pymodule]
fn _spectrum_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decode_code_spec_bytes_fast, m)?)?;
    Ok(())
}
