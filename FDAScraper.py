#python3
'''
date: July 2018

Class Checker is better to be used for getting historical data
and class Newsroomscraper for getting in realtime data
'''
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
import requests
import time
from twilio.rest import Client

BASE_URL = 'https://www.fda.gov'

url_approving = 'https://www.fda.gov/drugs/informationondrugs/ucm412998.htm'
   
URL_APPROVED = 'https://www.fda.gov/drugs/developmentapprovalprocess/druginnovation/ucm592464.htm'

FDA_NEWSROOM = 'https://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/default.htm?Page={}'

HEADER ={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.75 Safari/537.36'}

#authentification for twilio api
account_sid = "BLABLALBA"
auth_token = "BALABALBA"

#mongo staff
CONNECTION = MongoClient('mongodb://localhost:27017/my_database')

db = CONNECTION.my_database

announcements = db.announcements

approvals = db.approvals

HistoricalApprovals = db.HistoricalApprovals

HistAppro = db.HistAppro

patterns = ['The FDA granted approval of .*? to (.*?)[.]','The FDA granted the approval of .*? to (.*?)[.]','approval of .*? was granted to (.*?)[.]','The FDA granted this approval to (.*?)[.]','approval of .*? to (.*?)[.]', 'marketed by (.*?) based in', 'marketed by (.*?) of', 'manufactured by (.*?) based in']

HISTORICAL_URLS  = ['https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm592464.htm', 'https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm537040.htm', 'https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm483775.htm', 'https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm430302.htm']

class Checker():
    '''
    Class for checking storing and retrieving data from FDA susing URL_APPROVED
    but for that url data are updated in few days
    but this data can be used for analysis because it is much easier to extract name of Company and drug name from URL_APPROVED
    '''
    def __init__(self, URL = URL_APPROVED, HEADER = HEADER):
        
        self.URL = URL
        self.HTML = ''
        self.HEADER = HEADER 
    
    def get_html(self):
        '''
        send requests and will set s
        '''
        self.HTML =  requests.get(self.URL, headers = self.HEADER).text
        
    def soupify(self):
        '''
        returns BeautifulSoup object from self.HTML
        '''
        return BeautifulSoup(self.HTML, 'lxml')
    
    def get_tds(self):
        '''
        returns list of tds as BeautifulSoup objects
        '''
        return self.soupify().findAll('td')
    
    def get_fresh_tds(self):
        '''
        send requests and returns tds
        '''
        self.get_html()
        return self.get_tds()
    
    def get_groups(self):
        '''
        call get_fresh_tds and make groups from five items
        '''
        return list(zip(*(iter(self.get_fresh_tds()),)*5))
    
    def cleanify_one(self, rawData):
        '''
        will clean rawData (rawData are item from self.get_groups()) and returns json
        '''
        No = int(rawData[0].text.replace('.',''))
        DrugName = rawData[1].text
        ActiveIngredient = rawData[2].text
        Date = rawData[3].text
        Use = str(rawData[4]).split('<br')[0].replace('<td>', '')
        a_list = rawData[4].findAll('a')
        Links = {item.text: BASE_URL + item.get('href') for item in a_list}
        return {'No':No, 'DrugName': DrugName, 'ActiveIngredient': ActiveIngredient, 'Date': Date, 'Usage': Use, 'URLs': Links}
    
    def cleanify_all(self):
        '''
        for each in self.get_groups apply cleanify_one and returns list of dict
        '''
        return [self.cleanify_one(item) for item in self.get_groups()]
    
    def insert_into_database(self):
        '''
        get data from cleanify_all
        check if they are in collection and if not store them
        '''
        data = self.cleanify_all()
        for item in data:
            if  not list(approvals.find({'No':item.get('No')})):
                approvals.insert(item)
                
    def get_company_from_trial_snapshot(self,url):
        '''
        from drugs trial snapshot get company name
        '''
        r = requests.get(url, headers = self.HEADER)
        company = str([item for item in BeautifulSoup(r.text, 'lxml').findAll('p') if '2018' in item.text][0]).split('<br/>')[-2].replace('\r','').replace('\n','')
        return company
        
    def update_info(self, collection = 'approvals'):
        '''
        update info about document in collection
        '''
        collection  = eval(collection)
        data = collection.find({'URLs.Drug Trials Snapshot': {'$exists': 1}}, {'URLs.Drug Trials Snapshot':1})
        for item in data:
            company = self.get_company_from_trial_snapshot(item['URLs']['Drug Trials Snapshot'])
            collection.update({'_id':item['_id']},{'$set':{'Company':company}})
            
    def insert_historical(self):
        '''
        will find drugs for 2018, 2017, 2016, 2015 and add info about company
        '''
        for item in HISTORICAL_URLS:
            data = self.cleanify_all()
            for item in data:
                if  not list(approvals.find({'No':item.get('No')})):
                    HistAppro.insert(item)
        self.update_info('HistAppro')
        
class NewsroomScraper():
    '''
    First FDA publish approval on FDA_NEWSROOM
    '''
    
    def __init__(self, URL = FDA_NEWSROOM.format(1), HEADER = HEADER):
        
        self.URL = URL
        self.HTML = ''
        self.HEADER = HEADER
        self.approved_and_stored = [ item.get('origin') for item in list(announcements.find({},{'origin':1,'_id':0}))]
    
    def get_html(self):
        '''
        send requests and will set s
        '''
        self.HTML =  requests.get(self.URL, headers = self.HEADER).text
        
    def soupify(self):
        '''
        returns BeautifulSoup object from self.HTML
        '''
        return BeautifulSoup(self.HTML, 'lxml')
    
    def get_approvals(self, page = 1, url = FDA_NEWSROOM, base_url = BASE_URL):
        '''
        returns list of urls as BeautifulSoup objects and reverse last item in list is item with last date
        '''
        self.URL = url.format(page)
        self.get_html()
        return [base_url + item['href'] for item  in self.soupify().findAll('a') if 'approves' in item.text][::-1]  
    
    def get_data(self, url):
        '''
        will get data from annoucment
        '''
        self.URL = url
        self.get_html()
        html_content = self.soupify()
        ps = html_content.findAll('p')
        date = [item.text for item in ps if '2' in item.text][0]
        txt = html_content.find('div', class_ = 'release-text').text
        drug = ''
        try:
            drug = re.findall('approved (.*?) [(]', txt)[0]
        except:
            pass
        company = ''
        for item in patterns:
            try:
                com = re.search(item,txt).group(1).split(',')[0].split('based in')[0].split('The FDA')[0]
                if '-based' in com:
                    com = com.split('-based')[1]
                if com:
                    company = com
            except:
                pass
        return {'date':date, 'drug':drug, 'company':company, 'origin':url}
    
    def get_historical_data(self):
        '''
        will scrap all historical annoucnements
        '''
        result = []
        for item in [1,2,3,4]:
            approvals = self.get_approvals(item)
            result.extend([self.get_data(url) for url in approvals])
        return result[::-1]
    
    def get_historical_data_before(self):
        '''
        will scrap all historical annoucnements for 2017 and 2016
        '''
        result = []
        for element in ['https://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/default.htm?Page={}','https://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/2017/default.htm?Page={}', 'https://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/2016/default.htm?Page={}']:
            for item in [1,2,3,4]:
                approvals = self.get_approvals(item, element)
                result.extend([self.get_data(url) for url in approvals])
        return result[::-1]
    
    def get_historical_data_before_before(self):
        '''
        will scrap all historical annoucnements for 2015,2014,2013
        '''
        result = []
        for element in ['https://wayback.archive-it.org/7993/20170111002435/http://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/2015/default.htm?Page={}','https://wayback.archive-it.org/7993/20170111002446/http://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/2014/default.htm?Page={}', 'https://wayback.archive-it.org/7993/20170111002457/http://www.fda.gov/NewsEvents/Newsroom/PressAnnouncements/2013/default.htm?Page={}']:
            for item in [1,2,3,4]:
                approvals = self.get_approvals(item, element, 'https://wayback.archive-it.org')
                for url in approvals:
                    try:
                        data = self.get_data(url)
                        result.append(data)
                    except:
                        pass
        return result[::-1]
    
    def insert_historical_data(self):
        '''
        will call get_historical data and returned data will be stored in MongoDB
        '''
        data = self.get_historical_data()
        [announcements.insert(item) for item in data]
        
    def insert_historical_data_all(self):
        '''
        will call get_historical_before and get_historical_before_before data and returned data will be stored in MongoDB
        '''
        data = self.get_historical_data_before()
        [HistoricalApprovals.insert(item) for item in data]
        data = self.get_historical_data_before_before()
        [HistoricalApprovals.insert(item) for item in data]
        
    def send_message(self, message):
        '''
        send message via twilio
        '''
        client = Client(account_sid, auth_token)
        res = client.api.account.messages.create(to = "+421918629216", from_= 'FDA', body = message)
        return res
        
    def check(self):
        '''
        will check if url is in database or not and if not will get data and send sms 
        '''
        scraped = self.get_approvals()
        fresh = [item for item in scraped if not item in self.approved_and_stored]
        if fresh:
            for item in fresh:
                data = self.get_data(item)
                message = 'Company {}, Drug {}, Date {}'.format(data.get('company'), data.get('drug'), data.get('date'))
                self.send_message(message)
                announcements.insert(data)
                
    def run_forever(self):
        '''
        checks every  31 seconds website of FDA
        '''
        while True:
            self.check()
            time.sleep(31)
            
if __name__ == "__main__":
    nrs = NewsroomScraper()
    nrs.run_forever()
            
            
            
            
