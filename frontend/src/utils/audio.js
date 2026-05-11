/**
 * @file audio.js
 * @description PCM audio helpers used by the STT streaming pipeline.
 * All functions are pure and have no side effects on the DOM.
 */

export const TARGET_SAMPLE_RATE = 16000
export const STREAM_BUFFER_SIZE = 4096
export const SILENCE_THRESHOLD = 0.008
export const SILENCE_TIMEOUT_MS = 3000

export function toMono(audioBuffer) {
  if (audioBuffer.numberOfChannels === 1) {
    return audioBuffer.getChannelData(0)
  }

  const left = audioBuffer.getChannelData(0)
  const right = audioBuffer.getChannelData(1)
  const mono = new Float32Array(left.length)
  for (let i = 0; i < left.length; i++) {
    mono[i] = (left[i] + right[i]) / 2
  }
  return mono
}

export function resample(input, inputSampleRate, outputSampleRate) {
  if (inputSampleRate === outputSampleRate) return input

  const ratio = inputSampleRate / outputSampleRate
  const outputLength = Math.round(input.length / ratio)
  const output = new Float32Array(outputLength)

  for (let i = 0; i < outputLength; i++) {
    const position = i * ratio
    const leftIndex = Math.floor(position)
    const rightIndex = Math.min(leftIndex + 1, input.length - 1)
    const weight = position - leftIndex
    output[i] = input[leftIndex] * (1 - weight) + input[rightIndex] * weight
  }

  return output
}

export function normalize(samples) {
  let peak = 0
  for (let i = 0; i < samples.length; i++) {
    const abs = Math.abs(samples[i])
    if (abs > peak) peak = abs
  }
  if (peak === 0) return samples

  const scale = Math.min(10, 0.98 / peak)
  if (Math.abs(scale - 1) < 1e-3) return samples

  const output = new Float32Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    output[i] = samples[i] * scale
  }
  return output
}

export function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i))
    }
  }

  let offset = 0
  writeString(offset, 'RIFF'); offset += 4
  view.setUint32(offset, 36 + samples.length * 2, true); offset += 4
  writeString(offset, 'WAVE'); offset += 4
  writeString(offset, 'fmt '); offset += 4
  view.setUint32(offset, 16, true); offset += 4
  view.setUint16(offset, 1, true); offset += 2
  view.setUint16(offset, 1, true); offset += 2
  view.setUint32(offset, sampleRate, true); offset += 4
  view.setUint32(offset, sampleRate * 2, true); offset += 4
  view.setUint16(offset, 2, true); offset += 2
  view.setUint16(offset, 16, true); offset += 2
  writeString(offset, 'data'); offset += 4
  view.setUint32(offset, samples.length * 2, true); offset += 4

  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

export function floatTo16BitPCM(samples) {
  const buffer = new ArrayBuffer(samples.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

export function computeRms(samples) {
  if (!samples.length) return 0
  let sum = 0
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i]
  }
  return Math.sqrt(sum / samples.length)
}

export async function convertToWav(blob, targetSampleRate) {
  const audioContext = new (window.AudioContext || window.webkitAudioContext)()
  try {
    const arrayBuffer = await blob.arrayBuffer()
    const decoded = await audioContext.decodeAudioData(arrayBuffer)
    const mono = toMono(decoded)
    const resampled = resample(mono, decoded.sampleRate, targetSampleRate)
    const normalized = normalize(resampled)
    return encodeWav(normalized, targetSampleRate)
  } finally {
    await audioContext.close()
  }
}

export function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}
