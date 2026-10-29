// Offline progressive enhancement: every chapter and full-size image is a normal link.
const printButton = document.querySelector('.print')
if (printButton) {
  printButton.hidden = false
  printButton.addEventListener('click', () => window.print())
}

const imageDialog = document.getElementById('image-dialog')
let imageTrigger = null
if (imageDialog && typeof imageDialog.showModal === 'function') {
  document.querySelectorAll('.zoom').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      const source = link.querySelector('img')
      const caption = link.closest('figure').querySelector('figcaption')
      imageTrigger = link
      imageDialog.querySelector('img').src = link.href
      imageDialog.querySelector('img').alt = source.alt
      imageDialog.querySelector('.dialog-caption').textContent = caption.textContent
      imageDialog.showModal()
      imageDialog.scrollTop = 0
    })
  })
  imageDialog.addEventListener('close', () => {
    imageDialog.querySelector('img').removeAttribute('src')
    imageTrigger?.focus({ preventScroll: true })
    imageTrigger = null
  })
  imageDialog.addEventListener('click', (event) => {
    if (event.target !== imageDialog) return
    const bounds = imageDialog.getBoundingClientRect()
    if (
      event.clientX < bounds.left ||
      event.clientX > bounds.right ||
      event.clientY < bounds.top ||
      event.clientY > bounds.bottom
    )
      imageDialog.close()
  })
}

const chapters = [...document.querySelectorAll('main > section, #choose')]
const chapterLinks = [...document.querySelectorAll('nav a')]
let navigationFrame = null
function updateChapterNavigation() {
  navigationFrame = null
  const readingLine = Math.max(80, window.innerHeight * 0.22)
  const current = chapters
    .filter((chapter) => chapter.getBoundingClientRect().top <= readingLine)
    .at(-1)
  chapterLinks.forEach((link) => {
    if (current && link.hash === '#' + current.id) link.setAttribute('aria-current', 'location')
    else link.removeAttribute('aria-current')
  })
}
function scheduleChapterNavigation() {
  if (navigationFrame === null) navigationFrame = requestAnimationFrame(updateChapterNavigation)
}
window.addEventListener('scroll', scheduleChapterNavigation, { passive: true })
window.addEventListener('resize', scheduleChapterNavigation)
window.addEventListener('load', scheduleChapterNavigation)
scheduleChapterNavigation()

let closedBeforePrint = []
window.addEventListener('beforeprint', () => {
  if (imageDialog?.open) imageDialog.close()
  if (!closedBeforePrint.length)
    closedBeforePrint = [...document.querySelectorAll('details:not([open])')]
  closedBeforePrint.forEach((details) => {
    details.open = true
  })
})
window.addEventListener('afterprint', () => {
  closedBeforePrint.forEach((details) => {
    details.open = false
  })
  closedBeforePrint = []
})
