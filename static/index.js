
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./service-worker.js')
    .then(function(registration) {
        console.log('Service Worker registered with scope:', registration.scope);
        registration.onupdatefound = function() {
            const installingWorker = registration.installing;
            installingWorker.onstatechange = function() {
                if (installingWorker.state === 'installed') {
                    if (navigator.serviceWorker.controller) {
                        console.log('New content is available; please refresh.');
                        navigator.serviceWorker.addEventListener('controllerchange', function() {
                            window.location.reload();
                        });
                    } else {
                        console.log('Content is cached for offline use.');
                    }
                }
            };
        };
    })
    .catch(function(error) {
        console.log('Service Worker registration failed:', error);
    });
    navigator.serviceWorker.addEventListener('controllerchange', function() {
        console.log('Controller change detected. Reloading page.');
        window.location.reload();
    });
}

fetch('./categories.json')
.then(response => response.json())
.then(categories => {
    const selectElement = document.getElementById('parody');
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = `原作:${category}`;
        option.textContent = `${category}`;
        selectElement.appendChild(option);
    });
})
.catch(error => console.error('Error loading categories:', error));

const themeToggle = document.getElementById('theme-toggle');
const currentTheme = localStorage.getItem('theme') || 'light';
const setTheme = (theme) => {
    document.body.className = theme;
    localStorage.setItem('theme', theme);
    themeToggle.textContent = theme === 'dark' ? 'ライトモード' : 'ダークモード';
};
themeToggle.addEventListener('click', () => {
    const newTheme = document.body.className === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
});
setTheme(currentTheme)

document.addEventListener('DOMContentLoaded', () => {
    const pasteButton = document.getElementById('paste-button');
    const inputField = document.getElementById('nid');

    pasteButton.addEventListener('click', async () => {
        try {
            const clipboardText = await navigator.clipboard.readText();
            if (clipboardText) {
                inputField.value = clipboardText;
            }
        } catch (error) {
            console.log('クリップボードのアクセスに失敗しました。ブラウザの設定を確認してください。');
        }
    });
});

document.getElementById('scrape-form').addEventListener('submit', function(e) {
    e.preventDefault();
    var url = document.getElementById('nid').value;
    var submitBtn = document.getElementById('submit-btn');
    var progressBar = document.getElementById('progress-bar');
    var errorMessage = document.getElementById('error-message');
    const topBar = document.getElementById('progress-bar-top');
    const titleElement = document.getElementById('novel-title');
    const circle = document.getElementById('progress-circle');
    const downloadContainer = document.getElementById('download-container');
    if (downloadContainer) {
        downloadContainer.remove();
    }

    submitBtn.disabled = true;
    topBar.style.display = 'flex';
    progressBar.style.display = 'block';
    progressBar.querySelector('.progress-bar').style.width = '0%';
    progressBar.querySelector('.progress-bar').textContent = '0%';
    progressBar.querySelector('.progress-bar').setAttribute('aria-valuenow', 0);
    errorMessage.style.display = 'none';

    fetch('/start-scraping', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({url: url}),
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            checkProgress(data.nid);
        })
        .catch(error => {
            errorMessage.textContent = error.message;
            errorMessage.style.display = 'block';
            submitBtn.disabled = false;
            progressBar.style.display = 'none';
            topBar.style.display = 'none';
        });
});

function checkProgress(nid) {
    const topBar = document.getElementById('progress-bar-top');
    const circle = document.getElementById('progress-circle');
    const titleElement = document.getElementById('novel-title');
    circle.style.opacity = '100';
    fetch(`/progress/${nid}?t=${new Date().getTime()}`)
         .then(response => response.json())
         .then(data => {
             var progressBar = document.querySelector('.progress-bar');
             progressBar.style.width = data.progress + '%';
             progressBar.textContent = data.progress + '%';
             progressBar.setAttribute('aria-valuenow', data.progress);
             
             circle.setAttribute('data-progress', data.progress);
             circle.style.background = `conic-gradient(#007bff ${data.progress}%, lightgray ${data.progress}%)`;
             titleElement.textContent = `${data.title}`;

             if (data.progress < 100) {
                 setTimeout(() => checkProgress(nid), 5000);
             } else {
                   circle.style.opacity = '0';
                   const openButton = document.createElement("button");
                   openButton.className = "open-button";
                   openButton.textContent = "開く";
                   openButton.onclick = function () {
                       circle.setAttribute('data-progress', 0);
                       circle.style.background = 'conic-gradient(#007bff 0%, lightgray 0%)';
                       circle.classList.remove('complete');
                       circle.textContent = '';
                       titleElement.textContent = '';
                       topBar.style.display = 'none';
                       window.open(`/download/${nid}`, "_blank");
                   }
                    topBar.appendChild(openButton);
                   document.getElementById('progress-bar').style.display = 'none';
                   showDownloadLink(nid);
                   document.getElementById('submit-btn').disabled = false;
             }
         })
         .catch(error => {
             console.error('Error:', error);
         });
}

function showDownloadLink(nid) {
    var downloadLink = document.createElement('a');
    downloadLink.href = `/download/${nid}`;
    downloadLink.textContent = 'ダウンロード';
    downloadLink.className = 'btn btn-success mt-3';
    downloadLink.target = '_blank';

    var container = document.createElement('div');
    container.id = 'download-container';
    container.style.textAlign = 'center';
    container.appendChild(downloadLink);
    document.getElementById('converter').appendChild(container);
}
document.addEventListener('DOMContentLoaded', function() {
    const toggleFilterBtn = document.getElementById('toggle-filter');
    const filterOptions = document.getElementById('filter-options');
    const buttonTextSpan = toggleFilterBtn.querySelector('span');
    const buttonIcon = toggleFilterBtn.querySelector('i');

    toggleFilterBtn.addEventListener('click', function() {
        const isHidden = filterOptions.style.display === 'none';
        filterOptions.style.display = isHidden ? 'block' : 'none';
        this.classList.toggle('active');
        buttonTextSpan.textContent = isHidden ? '絞り込みオプションを非表示 ' : '絞り込みオプションを表示 ';
    });
});
document.getElementById('search-form').addEventListener('submit', function(e) {
    e.preventDefault();
    var word = document.getElementById('word').value;
    var checkedR18 = document.getElementById('r18').checked;
    var parody = document.getElementById('parody').value;
    var type = document.getElementById('type').value;
    var searchResult = document.getElementById('search-result');
    var searchResultContent = document.querySelector('.search-result');
    var searchBtn = document.getElementById('search-btn');

    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 検索中...';
    
    var bodyParams = new URLSearchParams({
        word: word,
        parody: parody,
        type: type,
        mode: checkedR18 ? 'search_r18' : 'search'
    });
    
    var filterParams = [
    'rensai_s1', 'rensai_s2', 'rensai_s4', 'mozi2', 'mozi1', 'mozi2_all', 'mozi1_all', 'rate2', 'rate1', 'soupt2', 'soupt1', 'f2', 'f1', 're2', 're1', 'v2', 'v1', 'r2', 'r1', 't2', 't1', 'd2', 'd1'
    ];
    
    filterParams.forEach(function(param) {
        const filterParam = document.querySelector(`input[name="${param}"]`);
        if (filterParam) {
            if (filterParam.type === 'checkbox') {
                if (filterParam.checked) {
                    bodyParams.append(param, "1");
                }
            } else if (filterParam.value) {
                bodyParams.append(param, filterParam.value);
            }
        }
    });

    fetch('/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: bodyParams
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        searchResultContent.innerHTML = '';
        data.results.forEach(result => {
            var listItem = document.createElement('div');
            listItem.className = 'search-result-item';
        
            var header = document.createElement('div');
            header.className = 'search-result-header';
            header.innerHTML = `
                <div>
                    <h3>${result.title}</h3>
                    <span class="badge badge-status badge-status-${result.status}">${result.status}</span>
                    <span class="badge badge-evaluation">評価 ${result.evaluation}</span>
                </div>
                <i class="fas fa-chevron-down"></i>
            `;
            
            var content = document.createElement('div');
            content.className = 'search-result-content';
            
            const createTags = (tags, className) => {
                return tags.map(tag => `<span class="tag ${className}">${tag}</span>`).join('');
            };
            content.innerHTML = `
                <div class="info-grid">
                    <div class="info-item">
                        <strong>作者</strong>
                        <span>${result.author}</span>
                    </div>
                    <div class="info-item">
                        <strong>${result.parody[0]}</strong>
                        <span>${result.parody[1]}</span>
                    </div>
                    <div class="info-item">
                        <strong>最新話</strong>
                        <span>${result.latest}</span>
                    </div>
                    <div class="info-item">
                        <strong>更新日時</strong>
                        <span>${result.updated_day}</span>
                    </div>
                    <div class="info-item">
                        <strong>総文字数</strong>
                        <span>${result.words}</span>
                    </div>
                    <div class="info-item">
                        <strong>お気に入り</strong>
                        <span>${result.favs}</span>
                    </div>
                </div>
                <div class="description">
                    <p>${result.description}</p>
                </div>
                ${result.alert_keywords && result.alert_keywords.length > 0 ? `
                    <div class="tags-container">
                        <div>
                            <div class="tags-title">警告タグ</div>
                            ${createTags(result.alert_keywords, 'tag-alert')}
                        </div>
                    </div>
                ` : ''}
                ${result.keywords && result.keywords.length > 0 ? `
                    <div class="tags-container">
                        <div>
                            <div class="tags-title">タグ</div>
                            ${createTags(result.keywords, 'tag-keyword')}
                        </div>
                    </div>
                ` : ''}
                <div class="search-result-actions">
                    <button class="btn btn-primary read-button">小説を読む</button>
                    <button class="btn btn-secondary input-url-button" data-link="${result.link}">小説URLに入力</button>
                </div>
            `;
            
            listItem.appendChild(header);
            listItem.appendChild(content);
            
            header.addEventListener('click', function() {
                content.classList.toggle('active');
                header.querySelector('i').classList.toggle('fa-chevron-up');
            });
            
            content.querySelector('.read-button').addEventListener('click', function() {
                window.open(`https:${result.link}`, '_blank');
            });
            
            content.querySelector('.input-url-button').addEventListener('click', function() {
                document.getElementById('nid').value = `https:${this.getAttribute('data-link')}`;
            });
            
            searchResultContent.appendChild(listItem);
        });
        searchResult.style.display = 'block';
    })
    .catch(error => {
        searchResultContent.innerHTML = '<p class="alert alert-danger">エラーが発生しました: ' + error.message + '</p>';
        searchResult.style.display = 'block';
    })
    .finally(() => {
        searchBtn.disabled = false;
        searchBtn.innerHTML = '検索';
    });
});

