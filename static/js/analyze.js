/* Analyze page: item-level CNN insights + optional admin training controls */

var isAdminUser = window.IS_ADMIN === true;
var previewObjectUrl = null;

function analyzeWithCnn() {
  var input = document.getElementById('cnnImageInput');
  var resultText = document.getElementById('cnnResultText');
  var insightPanel = document.getElementById('cnnInsightPanel');
  var button = document.getElementById('cnnAnalyzeBtn');

  if (!input || !resultText || !insightPanel || !button) return;
  if (!input.files || !input.files.length) {
    showToast('Image required', 'Please select an image to analyze with CNN.');
    return;
  }

  var formData = new FormData();
  formData.append('image', input.files[0]);

  button.disabled = true;
  resultText.textContent = 'Running CNN analysis...';
  insightPanel.textContent = 'Analyzing item details and recycling suitability...';

  fetch('/api/analyze/cnn', {
    method: 'POST',
    body: formData
  })
    .then(function(r) {
      return r.json().then(function(payload) {
        if (!r.ok) throw new Error(payload.error || 'CNN analysis failed');
        return payload;
      });
    })
    .then(function(result) {
      var confidence = Math.round((result.confidence || 0) * 100);
      var statusTone = result.status === 'Verified' ? 'High confidence' : 'Needs review';
      resultText.textContent = 'Prediction: ' + result.predictedType + ' | Confidence: ' + confidence + '% | ' + statusTone + ' | Model: ' + (result.model || 'Unknown');

      var recycleBadgeClass = result.recyclable ? 'badge-default' : 'badge-destructive';
      var recycleLabel = result.recycleLabel || (result.recyclable ? 'Useful for recycling' : 'Not suitable for direct recycling');
      insightPanel.innerHTML =
        '<div class="space-y-2">' +
          '<div class="flex items-center justify-between gap-2">' +
            '<p class="text-sm font-medium">Item information</p>' +
            '<span class="badge ' + recycleBadgeClass + '">' + recycleLabel + '</span>' +
          '</div>' +
          '<p>' + (result.itemInfo || 'No additional item information available.') + '</p>' +
          '<p><strong>Confidence note:</strong> ' + (result.confidenceNote || 'No confidence guidance available.') + '</p>' +
          '<p><strong>Guidance:</strong> ' + (result.guidance || 'Please segregate carefully before disposal.') + '</p>' +
        '</div>';

      showToast('CNN analysis complete', 'Predicted class: ' + result.predictedType);
    })
    .catch(function(err) {
      resultText.textContent = err.message;
      insightPanel.textContent = 'Could not determine recycling suitability for this item.';
      showToast('CNN analysis failed', err.message);
    })
    .finally(function() {
      button.disabled = false;
    });
}

function handleCnnInputChange() {
  var input = document.getElementById('cnnImageInput');
  var resultText = document.getElementById('cnnResultText');
  var insightPanel = document.getElementById('cnnInsightPanel');
  var previewImage = document.getElementById('cnnPreviewImage');
  var previewPlaceholder = document.getElementById('cnnPreviewPlaceholder');
  if (!input || !resultText || !insightPanel || !previewImage || !previewPlaceholder) return;

  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = null;
  }

  if (!input.files || !input.files.length) {
    resultText.textContent = 'Upload an image to run CNN prediction.';
    insightPanel.textContent = 'Item details and recycling usefulness will appear here after analysis.';
    previewImage.classList.add('hidden');
    previewImage.removeAttribute('src');
    previewPlaceholder.classList.remove('hidden');
    return;
  }

  previewObjectUrl = URL.createObjectURL(input.files[0]);
  previewImage.src = previewObjectUrl;
  previewImage.classList.remove('hidden');
  previewPlaceholder.classList.add('hidden');

  resultText.textContent = 'Selected: ' + input.files[0].name + '. Click "Analyze image with CNN".';
  insightPanel.textContent = 'Ready to analyze. Click the button to get item details and recycling suitability.';
}

function pollTrainingStatus() {
  var statusText = document.getElementById('trainingStatusText');
  var startButton = document.getElementById('startTrainingBtn');
  if (!statusText || !startButton) return;

  fetch('/api/model/train-status')
    .then(function(r) {
      return r.json().then(function(payload) {
        if (!r.ok) throw new Error(payload.error || 'Training status unavailable');
        return payload;
      });
    })
    .then(function(status) {
      statusText.textContent = status.message + (status.bestModelPath ? ' Best: ' + status.bestModelPath : '');
      startButton.disabled = status.status === 'running';
    })
    .catch(function(err) {
      statusText.textContent = err.message;
    });
}

function startModelTraining() {
  var pathField = document.getElementById('trainDataPath');
  var epochsField = document.getElementById('trainEpochs');
  var imgszField = document.getElementById('trainImgsz');
  var statusText = document.getElementById('trainingStatusText');
  var startButton = document.getElementById('startTrainingBtn');

  if (!pathField || !epochsField || !imgszField || !statusText || !startButton) return;
  if (!pathField.value.trim()) {
    showToast('Dataset path required', 'Provide your dataset YAML path to start training.');
    return;
  }

  startButton.disabled = true;
  statusText.textContent = 'Submitting training job...';

  fetch('/api/model/train', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataPath: pathField.value.trim(),
      epochs: parseInt(epochsField.value, 10) || 25,
      imgsz: parseInt(imgszField.value, 10) || 224
    })
  })
    .then(function(r) {
      return r.json().then(function(payload) {
        if (!r.ok) throw new Error(payload.error || 'Could not start training');
        return payload;
      });
    })
    .then(function() {
      showToast('Training started', 'CNN model training is now running.');
      pollTrainingStatus();
    })
    .catch(function(err) {
      statusText.textContent = err.message;
      startButton.disabled = false;
      showToast('Training start failed', err.message);
    });
}

function renderDatasetSummary(summary) {
  var node = document.getElementById('datasetValidationText');
  if (!node || !summary) return;
  var classes = summary.classCount || 0;
  node.textContent = 'Valid dataset. data.yaml: ' + summary.resolvedPath + ' | classes: ' + classes + ' | train: ' + summary.train + ' | val: ' + summary.val;
}

function validateDatasetPath() {
  var pathField = document.getElementById('trainDataPath');
  var statusNode = document.getElementById('datasetValidationText');
  if (!pathField || !statusNode) return;
  if (!pathField.value.trim()) {
    showToast('Path required', 'Enter your dataset YAML path first.');
    return;
  }

  statusNode.textContent = 'Validating dataset path...';
  fetch('/api/model/validate-dataset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataPath: pathField.value.trim() })
  })
    .then(function(r) {
      return r.json().then(function(payload) {
        if (!r.ok) throw new Error(payload.error || 'Validation failed');
        return payload;
      });
    })
    .then(function(response) {
      renderDatasetSummary(response.summary);
      showToast('Dataset valid', 'Your training dataset configuration is valid.');
    })
    .catch(function(err) {
      statusNode.textContent = err.message;
      showToast('Dataset invalid', err.message);
    });
}

function uploadDatasetZip() {
  var zipInput = document.getElementById('datasetZipInput');
  var pathField = document.getElementById('trainDataPath');
  var statusNode = document.getElementById('datasetValidationText');
  if (!zipInput || !pathField || !statusNode) return;
  if (!zipInput.files || !zipInput.files.length) {
    showToast('Zip required', 'Please select a dataset zip file.');
    return;
  }

  var formData = new FormData();
  formData.append('datasetZip', zipInput.files[0]);
  statusNode.textContent = 'Uploading dataset zip...';

  fetch('/api/model/upload-dataset-zip', {
    method: 'POST',
    body: formData
  })
    .then(function(r) {
      return r.json().then(function(payload) {
        if (!r.ok) throw new Error(payload.error || 'Zip upload failed');
        return payload;
      });
    })
    .then(function(payload) {
      pathField.value = payload.dataYamlPath;
      renderDatasetSummary(payload.summary);
      showToast('Dataset uploaded', 'data.yaml detected and auto-filled for training.');
    })
    .catch(function(err) {
      statusNode.textContent = err.message;
      showToast('Upload failed', err.message);
    });
}

document.addEventListener('DOMContentLoaded', function() {
  if (typeof lucide !== 'undefined') lucide.createIcons();
  var cnnImageInput = document.getElementById('cnnImageInput');
  if (cnnImageInput) {
    cnnImageInput.addEventListener('change', handleCnnInputChange);
  }
  if (isAdminUser) {
    pollTrainingStatus();
    setInterval(pollTrainingStatus, 12000);
  }
});
