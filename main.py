import threading
import time
import bs4
import requests
import StellarPlayer
import re
import urllib.parse

home_66ys_url = 'https://www.66yingshi.com/'

def concatUrl(url1, url2):
    splits = re.split(r'/+',url1)
    url = splits[0] + '//'
    if url2.startswith('/'):
        url = url + splits[1] + url2
    else:
        url = url + '/'.join(splits[1:-1]) + '/' + url2
    return url

#爬取影视页面中的播放链接地址
def parse_66ys_movie_magnet(url):
    print(url)
    urls = []
    res = requests.get(url,verify=False)
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
        selector = bs.select('#text table tbody')
        for item in selector:
            for child in item.children:
                if type(child) == bs4.element.Tag:
                    for a in child.select('tr > td > a'):
                        url = a.get('href')
                        if url.startswith('magnet'):
                            urls.append({'url':url,'title':a.string})
    else:
        print(res.text)
    return urls

#爬取所有分类
def parse_66ys_category():
    urls = []
    search_urls = []
    blacks = []
    res = requests.get(home_66ys_url,verify=False)
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'), 'html.parser')
        selector = bs.select('body > div:nth-child(2) > div.menutv > ul')
        for item in selector:
            for child in item.children:
                if type(child) == bs4.element.Tag:
                    child = child.find('a')
                    url = child.get('href')
                    if url:
                        if not re.match(r'http',url):
                            url = concatUrl(home_66ys_url, url)
                        if not child.string in blacks:
                            urls.append({'title':child.string,'url':url})
        #获取搜索页面链接
        selector = bs.select('#searchform')
        for item in selector:
            search_urls.append(concatUrl(urls[0]['url'], item.get('action')))
    return urls, search_urls

class m66ysplugin(StellarPlayer.IStellarPlayerPlugin):
    def __init__(self,player:StellarPlayer.IStellarPlayer):
        super().__init__(player)
        self.categories = []
        self.search_urls = []
        self.pages = []
        self.movies = []
        self.pageIndex = 0
        self.curCategory = ''
        self.curCategoryName = ''
        self.cur_page = '第' + str(self.pageIndex + 1) + '页'
        self.num_page = ''
        self.search_word = ''
        self.search_movies = []
        self.movie_urls = {}
        self.gbthread = threading.Thread(target=self._bgThread)

    #爬取某个分类页面的所有影视页面链接
    def parse_66ys_page_movies(self, page_url):
        urls = []
        res = requests.get(page_url,verify=False)
        if res.status_code == 200:
            bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
            titleKey = 'title'
            if self.curCategoryName != '首页':
                selector = bs.select('body > div:nth-child(4) > div.mainleft > div > div > ul a')
                titleKey = 'alt'
            else:
                selector = bs.select('body > div:nth-child(4) > div.tjlist > ul a')
            print(selector)
            for item in selector:
                url = urllib.parse.urljoin(home_66ys_url, item.get('href'))
                imgTag = item.select('img')
                if len(imgTag) != 0:
                    img = imgTag[0].get('src')
                    title = imgTag[0].get(titleKey)
                    urls.append({'title':title,'url':url,'img':img})
        return urls

    def search_66ys_page_movies(self, search_url):
        print(f'{search_url=}')
        urls = []
        res = requests.post(search_url,data={'show':'title,smalltext','tempid':1,'tbname':'Article','keyboard':self.search_word.encode('gb2312')},verify=False)
        if res.status_code == 200:
            bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
            selector = bs.select('body > div:nth-child(3) > div > div.mainleft ul')
            for ul in selector:
                for item in ul.children:
                    if type(item) == bs4.element.Tag:
                        href = item.select('div.listimg > a')[0].get('href')
                        url = urllib.parse.urljoin(home_66ys_url, href)
                        img = item.select('div.listimg > a > img')[0].get('src')
                        title = item.select('div.listimg > a > img')[0].get('alt')
                        urls.append({'title':title,'url':url,'img':img})
        else:
            print(res.text)
        return urls

    #爬取分类对应的所有页面数
    def parse_66ys_page_num(self,catUrl):
        if self.curCategoryName == '首页':
            return ['']
        print(catUrl)
        pages = []
        res = requests.get(catUrl,verify=False)
        if res.status_code == 200:
            bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
            selector = bs.select('body > div:nth-child(4) > div.mainleft > div > div > div:nth-child(1) a')
            for item in selector:
                href = item.get('href')
                if href:
                    href = urllib.parse.urljoin(catUrl, href)
                    pages.append(href)
        else:
            print(res.text)
        print(pages)
        if len(pages) > 0:
            last = pages[-1]
            pages.clear()
            m = re.match(catUrl+"index_(\d+).(\w+)", last)
            if m:
                num = int(m.group(1))
                pages.append(f'index.{m.group(2)}')
                pages += [f'index_{i}.{m.group(2)}' for i in range(2,num + 1)]
        return pages

    def _bgThread(self):
        while len(self.categories) == 0 and not self.isExit:
            self.parsePage()
            time.sleep(0.001)
        print(f'66ys bg thread:{self.gbthread.native_id} exit')
        # 刷新界面
        def update():
            if self.player.isModalExist('main'):
                self.updateLayout('main',self.makeLayout())
                self.loading(True)
        if hasattr(self.player,'queueTask'):
            self.player.queueTask(update)
        else:
            update()
       
    def stop(self):
        if self.gbthread.is_alive():
            print(f'66ys bg thread:{self.gbthread.native_id} is still running')
        return super().stop()

    def start(self):
        self.gbthread.start()
        return super().start()

    def parsePage(self):
        #获取分类导航
        if len(self.categories) == 0:
            self.categories, self.search_urls = parse_66ys_category()
        if len(self.categories) > 0:
            if not self.curCategory:
                self.curCategory, self.curCategoryName = self.categories[0]['url'],self.categories[0]['title']
            #获取该分类的所有页面数
            if len(self.pages) == 0:
                self.pages = self.parse_66ys_page_num(self.curCategory)
                self.num_page = '共' + str(len(self.pages)) + '页'
                if len(self.pages) > 0:
                    #获取分页视频资源
                    if len(self.movies) == 0:
                        url = concatUrl(self.curCategory, self.pages[self.pageIndex])
                        self.movies = self.parse_66ys_page_movies(url)  

    def makeLayout(self):
        nav_labels = []
        for cat in self.categories:
            nav_labels.append({'type':'link','name':cat['title'],'@click':'onCategoryClick'})

        grid_layout = {'group':
                            [
                                {'type':'image','name':'img','width':120,'height':150,'@click':'onMovieImageClick'},
                                {'type':'label','name':'title','hAlign':'center'},
                            ],
                            'dir':'vertical'
                      }
        controls = [
            {'group':nav_labels,'height':30},
            {'type':'space','height':10},
            {'group':
                [
                    {'type':'edit','name':'search_edit','label':'搜索'},
                    {'type':'button','name':'搜电影','@click':'onSearch'}
                ]
                ,'height':30
            },
            {'type':'space','height':10},
            {'type':'grid','name':'list','itemlayout':grid_layout,'value':self.movies,'marginSize':5,'itemheight':180,'itemwidth':120},
            {'group':
                [
                    {'type':'space'},
                    {'group':
                        [
                            {'type':'label','name':'cur_page',':value':'cur_page'},
                            {'type':'link','name':'上一页','@click':'onClickFormerPage'},
                            {'type':'link','name':'下一页','@click':'onClickNextPage'},
                            {'type':'link','name':'首页','@click':'onClickFirstPage'},
                            {'type':'link','name':'末页','@click':'onClickLastPage'},
                            {'type':'label','name':'num_page',':value':'num_page'},
                        ]
                        ,'width':0.45
                        ,'hAlign':'center'
                    },
                    {'type':'space'}
                ]
                ,'height':30
            },
            {'type':'space','height':5}
        ]
        return controls
        
    def show(self):
        controls = self.makeLayout()
        self.doModal('main',800,600,'',controls)

    def onModalCreated(self, pageId):
        print(f'dytt onModalCreated {pageId=}')
        if pageId == 'main':
            if len(self.movies) == 0:
                self.loading()

    def onSearchInput(self,*args):
        print(f'{self.search_word}')

    def onSearch(self,*args):
        self.search_word = self.player.getControlValue('main','search_edit')
        if len(self.search_urls) > 0:
            url = self.search_urls[0]
            self.search_movies = self.search_66ys_page_movies(url)
            print(self.search_movies)
            if len(self.search_movies) > 0:
                grid_layout = {'group':
                            [
                                {'type':'image','name':'img','width':120,'height':150,'@click':'onMovieImageClick'},
                                {'type':'label','name':'title','hAlign':'center'},
                            ],
                            'dir':'vertical'
                      }
                controls = {'type':'grid','name':'list','itemlayout':grid_layout,'value':self.search_movies,'marginSize':5,'itemheight':180,'itemwidth':120}
                if not self.player.isModalExist('search'):
                    self.doModal('search',800,600,self.search_word,controls)
                else:
                    self.player.updateControlValue('search','list',self.search_movies)
            else:
                self.player.toast('main',f'没有找到 {self.search_word} 相关的资源')
    

    def onCategoryClick(self,pageId,control,*args):
        for cat in self.categories:
            if cat['title'] == control:
                if cat['url'] != self.curCategory:
                    self.curCategory, self.curCategoryName = cat['url'], cat['title']
                    self.pageIndex = 0
                    #获取新分类的页面数
                    self.loading()
                    self.pages = self.parse_66ys_page_num(self.curCategory)
                    self.num_page = num_page = '共' + str(len(self.pages)) + '页'
                    self.player.updateControlValue('main','num_page',num_page)
                    self.selectPage()
                    self.loading(True)
                break
        
    def onMovieImageClick(self, pageId, control, item, *args):
        movie_name = ''
        if pageId == 'main':
            playUrl = parse_66ys_movie_magnet(self.movies[item]['url'])
            movie_name = self.movies[item]['title']
        elif pageId == 'search':
            playUrl = parse_66ys_movie_magnet(self.search_movies[item]['url'])
            movie_name = self.search_movies[item]['title']
        if len(playUrl) > 0:
            for item in playUrl:
                item['checked'] = False
            list_layout = [{'type':'label','name':'title','fontSize':12}, {'type':'link','name':'播放','width':30,'@click':'onPlayClick'}]
            if hasattr(self.player,'download'):
                list_layout.append({'type':'space','width':10})
                list_layout.append({'type':'link','name':'下载','width':30,'@click':'onDownloadClick'})
            layout = [
                    {'type':'list','name':'list','itemlayout':{'group':list_layout},'value':playUrl,'separator':True,'itemheight':30},
                    ]
            if len(playUrl) > 1 and self.player.version > '20230711111652':
                list_layout.insert(0, {'type':'check','width':30,'@click':'onSelectCheck'})
                layout.append({'group':[{'type':'space'},{'type':'button','name':'下载选中项','@click':'onClickDownloadSelected'},{'type':'space'}],'height':30})

            self.movie_urls[movie_name] = playUrl
            self.doModal(movie_name, 400, 500, movie_name, layout)
            self.movie_urls.pop(movie_name)
        else:
            self.player.toast('main','无可播放源')

    def onPlayClick(self, pageId, control, item, *args):
        if pageId in self.movie_urls:
            self.player.play(self.movie_urls[pageId][item]['url'])

    def onSelectCheck(self, pageId, control, item, *args):
        if pageId in self.movie_urls:
            self.movie_urls[pageId][item]['checked'] = not self.movie_urls[pageId][item]['checked']
           
    
    def onDownloadClick(self, pageId, control, item, *args):
        if pageId in self.movie_urls:
            self.player.download(self.movie_urls[pageId][item]['url'])

    def onClickDownloadSelected(self, pageId, *args):
        print(pageId)
        if pageId in self.movie_urls:
            hashs = []
            for item in self.movie_urls[pageId]:
                if item['checked']:
                    magnetUrl = item['url']
                    pos = magnetUrl.find('&')
                    if pos == -1:
                        pos = len(magnetUrl)
                    hash = magnetUrl[len('magnet:?xt=urn:btih:'):pos]
                    hashs.append(hash)
            print(hashs)
            if len(hashs) > 0 :
                magnets = 'magnets://urls=' + ','.join(hashs[0:len(hashs)]) + '&name=' + urllib.parse.quote(pageId)
                print(magnets)
                self.player.download(magnets)

    def selectPage(self):
        if len(self.pages) > self.pageIndex:
                self.movies.clear()
                self.player.updateControlValue('main','list',self.movies)
                url = concatUrl(self.curCategory, self.pages[self.pageIndex])
                self.movies = self.parse_66ys_page_movies(url)
                self.player.updateControlValue('main','list',self.movies)
                self.cur_page = page = '第' + str(self.pageIndex + 1) + '页'
                self.player.updateControlValue('main','cur_page',page)

    def onClickFormerPage(self, *args):
        if self.pageIndex > 0:
            self.pageIndex = self.pageIndex - 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickNextPage(self, *args):
        num_page = len(self.pages)
        if self.pageIndex + 1 < num_page:
            self.pageIndex = self.pageIndex + 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickFirstPage(self, *args):
        if self.pageIndex != 0:
            self.pageIndex = 0
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickLastPage(self, *args):
        if self.pageIndex != len(self.pages) - 1:
            self.pageIndex = len(self.pages) - 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def loading(self, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation('main', stop=stopLoading)

    def loadingPage(self, page, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation(page, stop=stopLoading)

    def onPlayerSearch(self, dispatchId, searchId, wd, limit):
        # 播放器搜索异步接口
        print(f'onPlayerSearch:{wd}')
        result = []
        self.search_word = wd
        url = 'https://www.66yingshi.com/e/search/index.php'
        if len(self.search_urls) > 0:
            url = self.search_urls[0]
        movies = self.search_66ys_page_movies(url)
        for item in movies:
            magnets = parse_66ys_movie_magnet(item['url'])
            if len(magnets) > 0:
                urls = []
                index = 1
                for magnet in magnets:
                    obj = []
                    obj.append('磁力' + str(index))
                    obj.append(magnet['url'])
                    urls.append(obj)
                    index = index + 1
                result.append({'urls':urls,'name':item['title'],'pic':item['img']})
            if len(result) >= limit:
                break
        self.player.dispatchResult(dispatchId, searchId=searchId, wd=wd, result=result)
    
def newPlugin(player:StellarPlayer.IStellarPlayer,*arg):
    plugin = m66ysplugin(player)
    return plugin

def destroyPlugin(plugin:StellarPlayer.IStellarPlayerPlugin):
    plugin.stop()
