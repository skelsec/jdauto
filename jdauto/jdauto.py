import asyncio
import shutil
import os
import subprocess
import shlex
from pathlib import Path

from multiplexor.operator import MultiplexorOperator
from multiplexor.logger.logger import mpexception, Logger

import traceback
from aiosmb import logger as smblogger
from aiosmb.commons.connection.url import SMBConnectionURL

from msldap.commons.url import MSLDAPURLDecoder
from msldap import logger as msldaplogger

from jackdaw.dbmodel import *
from jackdaw.gatherer.gatherer import Gatherer
import json
import logging

from aiosmb import logger as smblogger
from msldap import logger as msldaplogger
import multiprocessing
from jackdaw.common.cpucount import get_cpu_count


class JackdawAutoCollect:
	def __init__(self, agent_id, agentinfo, db_conn, socks_server_info, parallel_cnt = None, progress_queue = None):
		self.progress_queue = progress_queue
		self.agentinfo = agentinfo
		self.agent_id = agent_id
		self.multiplexor_server = '127.0.0.1'
		self.multiplexor_port = 9999
		self.db_conn = db_conn
		self.logger = logging.getLogger('jackdawautocollect.process')
		self.parallel_cnt = parallel_cnt
		self.domain_server = None
		self.socks_server_info = socks_server_info

		self.ldapenum = None
		self.ldapenum_task = None
		self.smbenum = None
		self.smbenum_task = None

	def get_domain_server(self):
		domains_raw = self.agentinfo.get('domains')
		domains = domains_raw.split(' | ')
		
		self.logger.info('Client domain: %s' % domains[0])
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
				'sh' : self.socks_server_info['listen_ip'],
				'sp' : self.socks_server_info['listen_port']
			}
			ldap_url = 'ldap+multiplexor-ntlm://{ds}/?proxytype=socks5&proxyhost={sh}&proxyport={sp}&authhost={ms}&authport={mp}&authagentid={ai}'.format(**info)
			smb_url = 'smb+multiplexor-ntlm://{ds}/?proxytype=socks5&proxyhost={sh}&proxyport={sp}&authhost={ms}&authport={mp}&authagentid={ai}'.format(**info)
			self.logger.info(ldap_url)
			self.logger.info(smb_url)
			smb_mgr = SMBConnectionURL(smb_url)
			ldap_mgr = MSLDAPURLDecoder(ldap_url)
			
			#self.ldapenum = LDAPEnumeratorManager(self.db_conn, ldap_mgr, agent_cnt=self.parallel_cnt, progress_queue=self.progress_queue)
			#self.logger.info('Enumerating LDAP')
			#self.ldapenum_task = asyncio.create_task(self.ldapenum.run())
			#
			#adifo_id = await self.ldapenum_task
			#if adifo_id is None:
			#	raise Exception('LDAP enumeration failed!')
			#self.logger.info('ADInfo entry successfully created with ID %s' % adifo_id)
			#
			#self.logger.info('Enumerating SMB')
			#self.smbenum = SMBGathererManager(smb_mgr, worker_cnt=self.parallel_cnt, progress_queue = self.progress_queue)
			#self.smbenum.gathering_type = ['all']
			#self.smbenum.db_conn = self.db_conn
			#self.smbenum.target_ad = adifo_id
			#self.smbenum_task = asyncio.create_task(self.smbenum.run())
			#
			#await self.smbenum_task

			work_dir = './workdir'

			with multiprocessing.Pool() as mp_pool:
				gatherer = Gatherer(
					self.db_conn, 
					work_dir, 
					ldap_url, 
					smb_url, 
					ldap_worker_cnt=None, 
					smb_worker_cnt=None, 
					mp_pool=mp_pool, 
					smb_gather_types=['all'], 
					progress_queue=self.progress_queue, 
					show_progress=False,
					calc_edges=True,
					dns=None
				)
				res, err = await gatherer.run()
				if err is not None:
					raise err
			return True
		except:
			logging.exception('Failed to run scan!')
			return False

	async def run(self):
		self.domain_server = self.get_domain_server()		
		if self.domain_server is None:
			logging.exception('Failed to get domain server!')
		
		res = await self.gather()
		if res is True:
			logging.info('Enumeration finished successfully')
		else:
			logging.info('Enumeration failed!')
			

class MultiplexorAutoStart(MultiplexorOperator):
	def __init__(self, connection_string, sqlite_folder_path, logger = None, parallel_cnt = None, progress_queue = None, progress_file_name = None, start_ui = False):
		MultiplexorOperator.__init__(self, connection_string, logger = logger)
		self.progress_queue = progress_queue
		self.progress_file_name = progress_file_name
		self.agent_tracker = {} #agentid -> info
		self.agent_info_tracker = {} #info -> agentid
		self.collection_tasks = {} #agentid -> (collection_task, collect obj)
		self.plugin_tracker = {}
		#self.db_conn = db_conn
		self.sqlite_folder_path = sqlite_folder_path
		self.parallel_cnt = parallel_cnt
		self.sqlite_progress_folder = None
		self.sqlite_finished_folder = None
		self.start_ui = start_ui

		try:
			self.sqlite_progress_folder = Path(self.sqlite_folder_path).joinpath('progress')
			self.sqlite_finished_folder = Path(self.sqlite_folder_path).joinpath('finished')
			self.sqlite_progress_folder.mkdir(parents=True, exist_ok=True)
			self.sqlite_finished_folder.mkdir(parents=True, exist_ok=True)
		except Exception as e:
			logging.exception('Failed to create folder structure! Will stop now')


	async def check_progress(self):
		logging.debug('Writing progress to %s' % self.progress_file_name)
		with open(self.progress_file_name, 'a+', newline = '') as f:
			f.write('\r\n')
			while True:
				try:
					res = await asyncio.wait_for(self.progress_queue.get(), timeout=1)
					f.write('%s \r\n' % str(res))
				except asyncio.TimeoutError:
					f.flush()
					continue
				except asyncio.CancelledError:
					f.flush()
					return
				except Exception as e:
					logging.debug('status file writer error! %s' % e)
					try:
						f.flush()
					except:
						pass
					return

	async def on_agent_connect(self, agent_id, agentinfo):
		try:
			logging.info('Agent connected! %s' % agent_id)
			if agentinfo is None:
				return
			logging.info(agentinfo)
			self.collection_tasks[agent_id] = asyncio.create_task(self.start_jackdaw_enum(agent_id, agentinfo))

		except:
			traceback.print_exc()
			#await self.logger.exception()

	async def start_jackdaw_enum(self, agent_id, agentinfo):
		try:
			db_filename = 'jackdaw_%s.db' % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
			db_file_path = Path(self.sqlite_progress_folder).joinpath(db_filename)
			db_conn = 'sqlite:///%s' % (db_file_path)
			create_db(db_conn)

			logging.info('Starting Jackdaw enum on %s' % agent_id)
			agentinfo_s = json.dumps(agentinfo)
			self.agent_tracker[agent_id] = agentinfo
			self.agent_info_tracker[agentinfo_s] = agent_id

			socks_server_info = await self.start_socks5(agent_id)

			collect = JackdawAutoCollect(agent_id, agentinfo, db_conn, socks_server_info, parallel_cnt=self.parallel_cnt, progress_queue=self.progress_queue)
			await collect.run()

			shutil.move(str(db_file_path), str(self.sqlite_finished_folder))
			logging.info('DB file moved!')
			if self.start_ui is True:
				cmd = shlex.split('jackdaw --sql %s nest --ip 0.0.0.0 --port 0' % db_conn)
				subprocess.run(cmd)

		except Exception as e:
			logging.exception('start_jackdaw_enum')

	async def on_agent_disconnect(self, agent_id):
		logging.info('Agent disconnected! %s' % agent_id)
		#self.scan_q.put((agent_id, None, None, "STOP"))
		if agent_id in self.collection_tasks:
			self.collection_tasks[agent_id].cancel()
		

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
		if self.progress_queue is None and self.progress_file_name is not None:
			logging.debug('Creating progress queue')
			self.progress_queue = asyncio.Queue()
		if self.progress_file_name is not None:
			asyncio.create_task(self.check_progress())
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
	import os
	import argparse
	parser = argparse.ArgumentParser(description='auto collector for MP')
	#parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity, can be stacked')
	#parser.add_argument('sql', help='SQL connection string in URL format')
	parser.add_argument('-q', '--sqlite_folder_path', default='./workdir', help='A folder to store enumeration results in')
	parser.add_argument('-m', '--multiplexor', default = 'ws://127.0.0.1:9999', help='multiplexor connection string in URL format')
	parser.add_argument('-p', '--parallel_cnt', default = get_cpu_count(), type=int, help='agent count')
	parser.add_argument('-o', '--progress-out-file', default = None, help='Filename to write progress to')
	parser.add_argument('-s', '--start-ui', action='store_true', help='Automatically start jackdaw UI after successful enumeration')

	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG)
	msldaplogger.setLevel(logging.INFO)
	smblogger.setLevel(1)
	logging.getLogger('websockets.server').setLevel(logging.ERROR)
	logging.getLogger('websockets.client').setLevel(logging.ERROR)
	logging.getLogger('websockets.protocol').setLevel(logging.ERROR)
	logging.getLogger('aiosmb').setLevel(100)
	logging.getLogger('asysocks').setLevel(100)

	
	mas = MultiplexorAutoStart(args.multiplexor, args.sqlite_folder_path, parallel_cnt=args.parallel_cnt, progress_file_name = args.progress_out_file, start_ui = args.start_ui)
	asyncio.run(mas.run())
	

if __name__ == '__main__':
	main()