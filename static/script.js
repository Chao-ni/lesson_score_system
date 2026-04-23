let dataset = []
let index = 0
let selectedScores = {}
let selectedTags = {}
let recommendedScores = {}

const DIMENSIONS = [
  "结构完整性",
  "内容准确性",
  "语言逻辑性",
  "素养导向性",
  "认知层次适切性",
  "教师能力发展性",
  "创新实用性"
]

function mapScore(rawScore) {
  const numericScore = Number(rawScore)

  if (Number.isNaN(numericScore)) {
    return ""
  }

  return Math.ceil(numericScore / 2)
}

function getRawScore(score, name) {
  if (score[name] && score[name]["得分"] != undefined) {
    return score[name]["得分"]
  }

  return ""
}

function getMappedScore(score, name) {
  if (score[name] && score[name]["得分"] != undefined) {
    const mappedScore = mapScore(score[name]["得分"])

    if (mappedScore !== "") {
      return mappedScore
    }

    return score[name]["得分"]
  }

  return ""
}

function getReason(score, name) {
  if (score[name] && score[name]["依据"]) {
    return score[name]["依据"].join("\n")
  }

  return ""
}

function setActiveScore(container, value) {
  container.querySelectorAll(".score-button").forEach(button => {
    button.classList.toggle("active", button.dataset.value === String(value))
  })
}

function setActiveTags(container) {
  const tagId = container.dataset.tagId
  const values = selectedTags[tagId] || []

  container.querySelectorAll(".tag-button").forEach(button => {
    button.classList.toggle("active", values.includes(button.dataset.value))
  })
}

function initButtonEvents() {
  document.querySelectorAll(".score-button").forEach(button => {
    button.addEventListener("click", () => {
      const container = button.closest(".score-item")
      const target = container.dataset.scoreId
      const value = button.dataset.value

      selectedScores[target] = value
      setActiveScore(container, value)
    })
  })

  document.querySelectorAll(".tag-button").forEach(button => {
    button.addEventListener("click", () => {
      const container = button.closest(".score-item")
      const target = container.dataset.tagId
      const value = button.dataset.value
      const currentValues = selectedTags[target] || []

      if (currentValues.includes(value)) {
        selectedTags[target] = currentValues.filter(item => item !== value)
      } else {
        selectedTags[target] = [...currentValues, value]
      }

      setActiveTags(container)
    })
  })
}

function loadNext() {
  fetch("/get_one")
    .then(res => res.json())
    .then(data => {
      if (!data) {
        alert("全部评分完成")
        return
      }

      dataset = [data.data]
      index = 0
      window.remain = data.remain
      update()
    })
}

function update() {
  if (index >= dataset.length) {
    alert("全部评分完成")
    return
  }

  const item = dataset[index]
  const score = item.score || {}

  document.getElementById("answer").innerText = item.predict_answer
  document.getElementById("progress").innerText = "剩余 " + window.remain + " 条"

  selectedScores = {}
  selectedTags = {}
  recommendedScores = {}

  DIMENSIONS.forEach((dimensionName, dimensionIndex) => {
    const scoreId = "s" + (dimensionIndex + 1)
    const container = document.querySelector(`.score-item[data-score-id="${scoreId}"]`)
    const recommendedScore = getMappedScore(score, dimensionName)
    const rawRecommendedScore = getRawScore(score, dimensionName)
    const reason = getReason(score, dimensionName)

    recommendedScores["m" + (dimensionIndex + 1)] = rawRecommendedScore
    selectedTags[scoreId + "_tags"] = []

    setActiveScore(container, "")
    setActiveTags(container)

    document.getElementById("ref" + (dimensionIndex + 1)).innerText =
      "模型评分：" + rawRecommendedScore + "\n理由：" + reason
  })
}

function validateScores() {
  for (let i = 1; i <= 7; i++) {
    if (!selectedScores["s" + i]) {
      alert("请为每个维度选择一个评分")
      return false
    }
  }

  return true
}
function submitScore() {
  if (!validateScores()) {
    return
  }

  const item = dataset[index]
  const data = {
    idx_id: item.idx_id
  }

  for (let i = 1; i <= 7; i++) {
    data["s" + i] = selectedScores["s" + i]
    data["s" + i + "_tags"] = selectedTags["s" + i + "_tags"] || []
    data["m" + i] = recommendedScores["m" + i] || ""
  }

  console.log("准备提交的数据:", data)

  fetch("/submit_score", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(data)
  })
    .then(async res => {
      const text = await res.text()
      console.log("submit_score 返回:", res.status, text)

      let jsonData = {}
      try {
        jsonData = JSON.parse(text)
      } catch (e) {
        throw new Error("后端返回的不是 JSON: " + text)
      }

      if (!res.ok) {
        throw new Error(jsonData.message || jsonData.error || "提交失败")
      }

      return jsonData
    })
    .then(() => {
      alert("提交成功")
      clearSelections()
      loadNext()
    })
    .catch(err => {
      console.error("提交失败:", err)
      alert("提交失败：" + err.message)
    })
}


function clearSelections() {
  selectedScores = {}
  selectedTags = {}
  recommendedScores = {}

  document.querySelectorAll(".score-button").forEach(button => {
    button.classList.remove("active")
  })

  document.querySelectorAll(".tag-button").forEach(button => {
    button.classList.remove("active")
  })
}

document.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault()
    submitScore()
  }
})

// function resetRound() {
//   if (!confirm("确定要开始新一轮评分吗？")) {
//     return
//   }

//   fetch("/reset_round", {
//     method: "POST"
//   })
//     .then(res => res.json())
//     .then(res => {
//       alert("已创建新评分轮次：" + res.table)
//       location.reload()
//     })
// }

initButtonEvents()
loadNext()
