<script setup lang="ts">
import { ref } from 'vue'

interface Source {
  id: number
  document: string
  title: string
  section: string
  content: string
}

interface Answer {
  answer: string
  sources: Source[]
  model: string | null
}

const askUrl = 'http://127.0.0.1:8000/ask'
const question = ref('')
const answer = ref<Answer | null>(null)
const submitting = ref(false)
const error = ref('')

function useExample(text: string) {
  question.value = text
}

async function ask() {
  const text = question.value.trim()
  if (!text || submitting.value) return

  submitting.value = true
  error.value = ''
  answer.value = null
  try {
    const response = await fetch(askUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text }),
    })
    const body: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = typeof body === 'object' && body !== null && 'detail' in body
        && typeof body.detail === 'string'
        ? body.detail
        : 'No se pudo responder la consulta.'
      throw new Error(detail)
    }
    answer.value = body as Answer
  } catch (requestError) {
    error.value = requestError instanceof TypeError
      ? 'No se pudo conectar con el backend. Confirmá que esté en ejecución y reintentá.'
      : requestError instanceof Error
        ? requestError.message
        : 'No se pudo responder la consulta.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main>
    <header>
      <p class="eyebrow">FinNova · documentación ficticia</p>
      <h1>FinAssist</h1>
      <p class="intro">Consultá procedimientos internos de ejemplo para productos, pagos y seguridad.</p>
    </header>

    <section class="notice" aria-label="Alcance de la demostración">
      Esta demostración no consulta cuentas ni ejecuta operaciones.
    </section>

    <section class="question-card" aria-labelledby="question-title" :aria-busy="submitting">
      <h2 id="question-title">¿Qué necesitás resolver?</h2>
      <form @submit.prevent="ask">
        <label for="question">Tu consulta</label>
        <textarea
          id="question"
          v-model="question"
          rows="4"
          required
          maxlength="2000"
          :disabled="submitting"
          placeholder="Escribí una pregunta sobre la documentación."
        ></textarea>
        <div class="examples" aria-label="Preguntas de ejemplo">
          <button type="button" class="example" :disabled="submitting" @click="useExample('¿Cómo bloqueo una tarjeta perdida?')">¿Cómo bloqueo una tarjeta perdida?</button>
          <button type="button" class="example" :disabled="submitting" @click="useExample('¿Dónde consulto el resumen?')">¿Dónde consulto el resumen?</button>
          <button type="button" class="example" :disabled="submitting" @click="useExample('¿Cómo reconozco un mensaje falso?')">¿Cómo reconozco un mensaje falso?</button>
        </div>
        <button class="submit" type="submit" :disabled="submitting || !question.trim()">
          {{ submitting ? 'Buscando y respondiendo…' : 'Consultar documentación' }}
        </button>
      </form>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>

    <section v-if="submitting" class="answer-card" aria-live="polite">
      <p role="status">Buscando en la documentación y preparando la respuesta…</p>
    </section>

    <section v-else-if="answer" class="answer-card" aria-labelledby="answer-title">
      <div class="answer-heading">
        <h2 id="answer-title">Respuesta</h2>
        <span v-if="answer.model" class="model">{{ answer.model }}</span>
      </div>
      <p class="answer-text">{{ answer.answer }}</p>

      <div class="sources">
        <h3>Fuentes de la respuesta</h3>
        <p class="source-note">Abrí cada referencia para leer el fragmento citado.</p>
        <ol v-if="answer.sources.length">
          <li v-for="source in answer.sources" :key="source.id">
            <details>
              <summary><span>[{{ source.id }}]</span> {{ source.title }}<span v-if="source.section"> · {{ source.section }}</span></summary>
              <p class="document">{{ source.document }}</p>
              <p class="source-content">{{ source.content }}</p>
            </details>
          </li>
        </ol>
        <p v-else class="source-note">No hay fuentes suficientes para responder esta consulta.</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(body) { margin: 0; min-width: 320px; background: #eef3f7; color: #142b43; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.5; }
main { max-width: 760px; margin: 0 auto; padding: 48px 20px 64px; }
header { padding: 0 4px; }
.eyebrow { margin: 0 0 12px; color: #31688d; font-size: .8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h1 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.5rem, 9vw, 4.5rem); font-weight: 600; letter-spacing: -.055em; line-height: .95; }
.intro { max-width: 560px; margin: 16px 0 0; color: #466077; font-size: 1.08rem; }
.notice { margin-top: 28px; padding: 12px 16px; border-left: 3px solid #6aa5c6; background: #e0edf4; color: #244860; font-size: .94rem; }
section:not(.notice) { margin-top: 24px; padding: 28px; border: 1px solid #cfdae3; background: #fff; box-shadow: 0 12px 30px rgb(31 71 96 / 7%); }
h2 { margin: 0 0 18px; font-size: 1.2rem; letter-spacing: -.015em; }
h3 { margin: 28px 0 4px; font-size: 1rem; }
label { display: block; margin-bottom: 8px; font-weight: 700; }
textarea { width: 100%; min-height: 112px; padding: 13px; border: 1px solid #92aabd; border-radius: 2px; color: inherit; resize: vertical; font: inherit; }
textarea::placeholder { color: #718497; }
textarea:focus-visible, button:focus-visible, summary:focus-visible { outline: 3px solid #277ca8; outline-offset: 3px; }
.examples { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
button { font: inherit; cursor: pointer; }
.example { padding: 5px 8px; border: 1px solid #b6c8d4; border-radius: 2px; background: #f8fafb; color: #2d5d7d; font-size: .83rem; text-align: left; }
.example:hover:not(:disabled) { border-color: #5488a9; background: #edf5f9; }
.submit { margin-top: 20px; padding: 11px 18px; border: 1px solid #0e547d; border-radius: 2px; background: #125d87; color: #fff; font-weight: 700; }
.submit:hover:not(:disabled) { background: #0c496c; }
button:disabled { cursor: not-allowed; opacity: .6; }
.error { margin: 16px 0 0; color: #9c2b2b; }
.answer-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.answer-heading h2 { margin: 0; }
.model { color: #5d7384; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .76rem; }
.answer-text { margin: 20px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.sources { margin-top: 28px; padding-top: 4px; border-top: 1px solid #d8e1e7; }
.source-note, .document { margin: 4px 0 0; color: #5a6d7c; font-size: .9rem; }
ol { margin: 16px 0 0; padding-left: 22px; }
li + li { margin-top: 9px; }
details { padding: 8px 0; }
summary { color: #1f5679; cursor: pointer; font-weight: 700; }
summary span { color: #587084; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .85em; }
.source-content { margin: 10px 0 0; padding: 12px; border-left: 2px solid #b5cfdf; background: #f4f8fa; color: #314b60; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 560px) { main { padding: 32px 16px 48px; } section:not(.notice) { padding: 20px; } .examples { display: grid; } .answer-heading { align-items: flex-start; flex-direction: column; gap: 5px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; } }
</style>
