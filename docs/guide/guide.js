// Progressive enhancement only: navigation, instructions and image links work without JS.
const printButton = document.querySelector('.print')
printButton.hidden = false
printButton.addEventListener('click', () => window.print())
const dialog = document.getElementById('image-dialog')
if (typeof dialog.showModal === 'function') {
  document.querySelectorAll('.zoom').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      const source = link.querySelector('img')
      dialog.querySelector('img').src = source.src
      dialog.querySelector('img').alt = source.alt
      dialog.querySelector('p').textContent = link
        .closest('figure')
        .querySelector('figcaption').textContent
      dialog.showModal()
      dialog.scrollTop = 0
    })
  })
}
let expandedBeforePrint = []
window.addEventListener('beforeprint', () => {
  expandedBeforePrint = [...document.querySelectorAll('details')].filter((item) => !item.open)
  expandedBeforePrint.forEach((item) => {
    item.open = true
  })
})
window.addEventListener('afterprint', () => {
  expandedBeforePrint.forEach((item) => {
    item.open = false
  })
})
