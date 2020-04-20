import asyncio

from multiplexor.operator import MultiplexorOperator
from multiplexor.logger.logger import mpexception, Logger

import traceback
import multiprocessing
from aiosmb import logger as smblogger
from aiosmb.commons.connection.url import SMBConnectionURL

from msldap.commons.url import MSLDAPURLDecoder
from msldap import logger as msldaplogger

from jackdaw.dbmodel import *
from jackdaw.gatherer.smb.smb import SMBGathererManager
from jackdaw.gatherer.ldap.aioldap import LDAPEnumeratorManager
import json
import logging

from aiosmb import logger as smblogger
from msldap import logger as msldaplogger


class JackdawAutoCollect(multiprocessing.Process):
	def __init__(self, agent_id, agentinfo, db_conn):
		multiprocessing.Process.__init__(self)
		self.agentinfo = agentinfo
		self.agent_id = agent_id
		self.multiplexor_server = '127.0.0.1'
		self.multiplexor_port = 9999
		self.db_conn = db_conn
		self.logger = logging.getLogger('jackdawautocollect.process')

		self.domain_server = None

	def setup_db(self):
		create_db(self.db_conn)

	def get_domain_server(self):
		domains_raw = self.agentinfo.get('domains')
		domains = domains_raw.split(' | ')
		
		logging.info('Client domain: %s' % domains[0])
		return domains[0]

	def gather(self):
		try:
			info = {
				'ds' : self.domain_server,
				'ms' : self.multiplexor_server,
				'mp' : self.multiplexor_port,
				'ai' : self.agent_id,
			}
			ldap_url = 'ldap+multiplexor-ntlm://{ds}/?proxytype=multiplexor&proxyhost={ms}&proxyport={mp}&proxyagentid={ai}&authhost={ms}&authport={mp}&authagentid={ai}'.format(**info)
			smb_url = 'smb+multiplexor-ntlm://{ds}/?proxytype=multiplexor&proxyhost={ms}&proxyport={mp}&proxyagentid={ai}&authhost={ms}&authport={mp}&authagentid={ai}'.format(**info)
			logging.info(ldap_url)
			logging.info(smb_url)
			smb_mgr = SMBConnectionURL(smb_url)
			ldap_mgr = MSLDAPURLDecoder(ldap_url)
		
			ldapenum = LDAPEnumeratorManager(self.db_conn, ldap_mgr, agent_cnt=5) # should be in args
			logging.info('Enumerating LDAP')
			adifo_id = ldapenum.run()
			logging.info('ADInfo entry successfully created with ID %s' % adifo_id)
			
			logging.info('Enumerating SMB')
			mgr = SMBGathererManager(smb_mgr)
			mgr.gathering_type = ['all']
			mgr.db_conn = self.db_conn
			mgr.target_ad = adifo_id
			mgr.run()
			return True
		except:
			logging.exception('Failed to run scan!')
			return False

	def run(self):
		self.domain_server = self.get_domain_server()
		self.setup_db()
		if self.domain_server is None:
			logging.exception('Failed to get domain server!')
		
		res = self.gather()
		if res is True:
			logging.info('Enumeration finished successfully')
		else:
			logging.info('Enumeration failed!')

class JackdawAutoCollectManager(multiprocessing.Process):
	def __init__(self, scan_q):
		multiprocessing.Process.__init__(self)
		self.scan_q = scan_q
		self.logger = logging.getLogger('jackdawautocollect.manager')


	def run(self):
		while True:
			data = self.scan_q.get()
			print('data_in')
			if data is None:
				return
			agent_id, agentinfo, db_conn = data
			autocollect = JackdawAutoCollect(agent_id, agentinfo, db_conn)
			autocollect.start()
			

class MultiplexorAutoStart(MultiplexorOperator):
	def __init__(self, connection_string, db_conn, scan_q, logger = None):
		MultiplexorOperator.__init__(self, connection_string, logger = logger)
		self.agent_tracker = {} #agentid -> info
		self.agent_info_tracker = {} #info -> agentid 
		self.plugin_tracker = {}
		self.db_conn = db_conn
		self.scan_q = scan_q

	async def on_agent_connect(self, agent_id, agentinfo):
		try:
			logging.info('Agent connected! %s' % agent_id)
			if agentinfo is None:
				return
			logging.info(agentinfo)
			await self.start_jackdaw_enum(agent_id, agentinfo)

		except:
			traceback.print_exc()
			#await self.logger.exception()

	async def start_jackdaw_enum(self, agent_id, agentinfo):
			logging.info('Starting Jackdaw enum on %s' % agent_id)
			agentinfo_s = json.dumps(agentinfo)
			self.agent_tracker[agent_id] = agentinfo
			self.agent_info_tracker[agentinfo_s] = agent_id

			self.scan_q.put((agent_id, agentinfo, self.db_conn))

	async def on_agent_disconnect(self, agent_id):
		logging.info('Agent disconnected! %s' % agent_id)

	async def on_plugin_start(self, agent_id, plugin_id):
		logging.info('Plugin started! %s %s' % (agent_id, plugin_id))

	async def on_plugin_stop(self, agent_id, plugin_id):
		logging.info('Plugin stopped! %s %s' % (agent_id, plugin_id))
	
	async def on_log(self, log):
		pass
		#logging.debug(str(log))

	async def on_server_connected(self, connection_string):
		logging.info('Connected to server %s' % connection_string)

	async def on_server_error(self, reason):
		logging.error('Failed to connect to server! Reason: %s' % reason)

	async def on_run(self):
		logging.info('Fetching agents')
		agentids = await self.list_agents()
		if len(agentids) == 0:
			logging.info('No agents connected currently')
		for agent_id in agentids:
			if agent_id not in self.agent_tracker:
				agentinfo = await self.info_agent(agent_id)
				agentinfo_s = json.dumps(agentinfo)
				if agentinfo_s not in self.agent_info_tracker:
					await self.start_jackdaw_enum(agent_id, agentinfo)

def main():
	import argparse
	parser = argparse.ArgumentParser(description='auto collector for MP')
	#parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity, can be stacked')
	parser.add_argument('sql', help='SQL connection string in URL format')
	parser.add_argument('multiplexor', help='multiplexor connection string in URL format')
	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG)
	msldaplogger.setLevel(logging.INFO)
	smblogger.setLevel(1)
	logging.getLogger('websockets.server').setLevel(logging.ERROR)
	logging.getLogger('websockets.client').setLevel(logging.ERROR)
	logging.getLogger('websockets.protocol').setLevel(logging.ERROR)

	scan_q = multiprocessing.Queue()
	mgr = JackdawAutoCollectManager(scan_q)
	mgr.start()

	mas = MultiplexorAutoStart(args.multiplexor, args.sql, scan_q)
	asyncio.run(mas.run())
	

if __name__ == '__main__':
	main()