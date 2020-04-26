import asyncio

from multiplexor.operator import MultiplexorOperator
from multiplexor.logger.logger import mpexception, Logger

import traceback
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


class JackdawAutoCollect:
	def __init__(self, agent_id, agentinfo, db_conn, parallel_cnt = None, progress_queue = None):
		self.progress_queue = progress_queue
		self.agentinfo = agentinfo
		self.agent_id = agent_id
		self.multiplexor_server = '127.0.0.1'
		self.multiplexor_port = 9999
		self.db_conn = db_conn
		self.logger = logging.getLogger('jackdawautocollect.process')
		self.parallel_cnt = parallel_cnt
		self.domain_server = None

		self.ldapenum = None
		self.ldapenum_task = None
		self.smbenum = None
		self.smbenum_task = None

	def setup_db(self):
		create_db(self.db_conn)

	def get_domain_server(self):
		domains_raw = self.agentinfo.get('domains')
		domains = domains_raw.split(' | ')
		
		logging.info('Client domain: %s' % domains[0])
		return domains[0]

	async def terminate(self):
		if self.ldapenum_task is not None:
			await self.ldapenum.terminate()
			self.ldapenum_task.cancel()
		if self.smbenum_task is not None:
			await self.smbenum.terminate()
			self.smbenum_task.cancel()
		

	async def gather(self):
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
			
			self.ldapenum = LDAPEnumeratorManager(self.db_conn, ldap_mgr, agent_cnt=self.parallel_cnt, progress_queue=self.progress_queue)
			logging.info('Enumerating LDAP')
			self.ldapenum_task = asyncio.create_task(self.ldapenum.run())
			try:
				adifo_id = await self.ldapenum_task
			except asyncio.CancelledError:
				return

			logging.info('ADInfo entry successfully created with ID %s' % adifo_id)
			
			logging.info('Enumerating SMB')
			self.smbenum = SMBGathererManager(smb_mgr, worker_cnt=self.parallel_cnt, progress_queue = self.progress_queue)
			self.smbenum.gathering_type = ['all']
			self.smbenum.db_conn = self.db_conn
			self.smbenum.target_ad = adifo_id
			self.smbenum_task = asyncio.create_task(self.smbenum.run())

			try:
				await self.smbenum_task
			except asyncio.CancelledError:
				return

			return True
		except:
			logging.exception('Failed to run scan!')
			return False

	async def run(self):
		self.domain_server = self.get_domain_server()
		self.setup_db()
		if self.domain_server is None:
			logging.exception('Failed to get domain server!')
		
		res = await self.gather()
		if res is True:
			logging.info('Enumeration finished successfully')
		else:
			logging.info('Enumeration failed!')
			

class MultiplexorAutoStart(MultiplexorOperator):
	def __init__(self, connection_string, db_conn, logger = None, parallel_cnt = None, progress_queue = None):
		MultiplexorOperator.__init__(self, connection_string, logger = logger)
		self.progress_queue = progress_queue
		self.agent_tracker = {} #agentid -> info
		self.agent_info_tracker = {} #info -> agentid
		self.collection_tasks = {} #agentid -> (collection_task, collect obj)
		self.plugin_tracker = {}
		self.db_conn = db_conn
		#self.scan_q = scan_q
		self.parallel_cnt = None

	#async def check_progress(self):
	#	while True:
	#		res = await self.progress_queue.get()
	#		print(str(res))

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

		collect = JackdawAutoCollect(agent_id, agentinfo, self.db_conn, parallel_cnt=self.parallel_cnt, progress_queue=self.progress_queue)
		self.collection_tasks[agent_id] = (asyncio.create_task(collect.run()), collect)
		#self.scan_q.put((agent_id, agentinfo, self.db_conn, "START"))

	async def on_agent_disconnect(self, agent_id):
		logging.info('Agent disconnected! %s' % agent_id)
		#self.scan_q.put((agent_id, None, None, "STOP"))
		if agent_id in self.collection_tasks:
			await self.collection_tasks[agent_id][1].terminate()
			await asyncio.sleep(1)
			self.collection_tasks[agent_id][0].cancel()
		

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
		#self.progress_queue = asyncio.Queue()
		#if self.progress_queue is not None:
		#	asyncio.create_task(self.check_progress())
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
	parser.add_argument('-m', '--multiplexor', default = 'ws://127.0.0.1:9999', help='multiplexor connection string in URL format')
	parser.add_argument('-p', '--parallel_cnt', default = 10, type=int, help='agent count')
	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG)
	msldaplogger.setLevel(logging.INFO)
	smblogger.setLevel(1)
	logging.getLogger('websockets.server').setLevel(logging.ERROR)
	logging.getLogger('websockets.client').setLevel(logging.ERROR)
	logging.getLogger('websockets.protocol').setLevel(logging.ERROR)
	logging.getLogger('aiosmb').setLevel(100)

	create_db(args.sql)

	mas = MultiplexorAutoStart(args.multiplexor, args.sql, parallel_cnt=args.parallel_cnt)
	asyncio.run(mas.run())
	

if __name__ == '__main__':
	main()