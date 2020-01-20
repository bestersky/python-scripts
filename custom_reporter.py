from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.callback import CallbackBase
try:
    import simplejson as json
except ImportError:
    import json
import time
import os

# to record taskname per server
taskid=''
global pid
global count_pid
global pid_stack
global pid_status
pid = ''
count_pid = 0
pid_status = ''
pid_stack = 0
class CallbackModule(CallbackBase):
    def create_logs(self):
        self.datetime=time.strftime("%Y-%m-%d_%H_%M")
        if not (os.path.exists("reports/raw")):
          os.makedirs('reports/raw')
        if not (os.path.exists('reports/raw/'+self.datetime)):
          os.makedirs('reports/raw/'+self.datetime)
        self.summary = open('reports/raw/'+self.datetime+'/summary_report_'+self.datetime+'.csv', 'w')
        self.report = open('reports/raw/'+self.datetime+'/report_'+self.datetime+'.csv', 'w')
    def custom_reporter(self, data, host):
        self.perhost_file = open('reports/raw/'+self.datetime+'/'+host+'_'+self.datetime+'.json', 'a')
        try:
             module_name=data['invocation']["module_name"]
        except:
             module_name=None

        if module_name == 'setup':
             # this is only availble in setup task, so you use to wirte host details, which will be at the start
             datetime=time.strftime("%Y-%m-%d %H:%M")
             try:
                ip=data['ansible_facts']['facter_ipaddress']
             except:
                ip='facter_ipaddress not found'

             try:
                fqdn=data['ansible_facts']['facter_fqdn']
             except:
                fqdn='facter_fqdn not found'

             try:
                osrel=data['ansible_facts']['facter_operatingsystemrelease']
             except:
                osrel='facter_operatingsystemrelease not found'

             try:
               os=data['ansible_facts']['facter_operatingsystem']
             except:
               os='facter_operatingsystem not found'

             perhost_file.write("\nDATE: {0}\nHost: {1}\nIP: {2}\nOS: {3} {4}\n============\n".format(datetime,fqdn,ip,os,osrel))
        else:
          if type(data) == dict:
            status='UNKNOWN'
            output=''
            cmd=''
            keyfound=False
            # get fields we are interested in
            if 'cmd' in data.keys():
              cmd=self._format_output(data['cmd'],'cmd')
            else:
              cmd=""
            if 'stdout' in data.keys():
              stdout=self._format_output(data['stdout'],'stdout')
            else:
              stdout=""
            if 'stderr' in data.keys():
              stderr=self._format_output(data['stderr'],'stderr')
            else:
              stderr=""
            if 'msg' in data.keys():
              msg=self._format_output(data['msg'],'msg')
            else:
              msg=""
            if 'rc' in data.keys():
              rc=self._format_output(data['rc'],'rc')
            else:
              rc=""
            if 'failed_when_result' in data.keys():
              failed=self._format_output(data['failed_when_result'],'failed')
            else:
              failed=""


            # if we find 'failed' then it's simple as setting it pass or fail.
            if 'failed_when_result' in data.keys():
                global pid_status
                if failed == True:
                  status='PASS'
                  keyfound=True
                  pid_status = status
                  if type(msg) == list:
                    msg=str(msg)
                  if type(msg) == bool:
                    msg=str(msg)
                  if stdout == '' and stderr == '':
                    if msg != []:
                      output=msg
                else:
                  status='FAIL'
                  keyfound=True
                  pid_status = status
                  if type(msg) == list or type(msg) == bool:
                    msg=str(msg)
                  if stdout == '' and  stderr == '':
                    output=msg
            else:
               keyfound=False

            # else we look at if its msg is a item data
            if not keyfound:
                output,status=self.itemOutput(msg)
                keyfound=True
                if status == '':
                  keyfound=False
            # at this stage, its not with_items or doesn't have 'failed' failed, so let check rc
            if not keyfound:
                if rc == 0:
                    status='PASS'
                    keyfound=True

            if not keyfound:
                 status='UNKNOWN'
                # TODO: ADD ANY OTHER USE CASES. IF reach here, then haven't captured this yet
                # not all ansibe tasks has bene used, so look into other use cases, if needed

            #print("\n{0}: {1}, {2}".format(field, output.replace("\\n","\n"), status))
            output = output+'\n'+stdout +'\n' + stderr
            if self.taskid != '':
              #print("\n{0}, {1}".format(host,status))
              outdata = { self.taskid: { 'status': status, 'output': output, 'cmd': cmd  }}
              #perhost_file.write("\n{0}, {1}".format(self.taskid,status))
              #perhost_file.write("\ncmd: {0}".format(cmd))
              #perhost_file.write("\noutput: {0}".format(output))
              self.summary.write("\n{0}, {1}, {2}, {3}".format(self.taskid,host,status,stdout))
              self.perhost_file.write(json.dumps(outdata)+'\n')

    def _format_output(self, output, field):
        # Strip unicode
        if type(output) == unicode:
            output = output.encode('ascii', 'replace')

        # If output is a dict
        if type(output) == dict:
            return json.dumps(output, indent=2)

        if type(output) == list and output == []:
            return ''

        # If output is a list of dicts
        if type(output) == list and type(output[0]) == dict:
            # This gets a little complicated because it potentially means
            # nested results, usually because of with_items.
            real_output = list()
            for index, item in enumerate(output):
                copy = item
                if type(item) == dict:
                     if field in item.keys():
                        copy[field] = self._format_output(item[field],field)
                real_output.append(copy)
            return real_output

        # If output is a list of strings
        if type(output) == list and type(output[0]) != dict:
            # Strip newline characters
            real_output = list()
            for item in output:
                if "\n" in item:
                    for string in item.split("\n"):
                        real_output.append(string)
                else:
                    real_output.append(item)

            # Reformat lists with line breaks only if the total length is
            # >75 chars
            if len("".join(real_output)) > 75:
                return "\n" + "\n".join(real_output)
            else:
                return " ".join(real_output)

        # Otherwise it's a string, just return it
        return output

    def setTaskID(self,taskname,iscon):
      self.taskid = taskname

    def itemOutput(self,msg):
    # def for iterating through with_items output, to get fail ro pass details per item
                if  type(msg) == list:
                  # this is  when item.results is printed out
                  all_item_output = ""
                  item_failed=False
                  for index, item in enumerate(msg):
                      if type(item) == dict:
                        if 'failed' in item.keys():
                          if item['failed']:
                            item_status='FAIL'
                            item_stdout = item['stderr']+' '+item['stdout']
                            item_failed=True
                          else:
                            item_status='PASS'
                            item_stdout = item['stdout']
                        else:
                          if item['rc'] == 0:
                            item_status='PASS'
                            item_stdout = item['stdout']
                          else:
                            item_status='FAIL'
                            item_stdout = item['stderr']+' '+item['stdout']
                            item_failed=True
                        all_item_output= all_item_output+"\nItem: "+item['item'] +', '+item_status+'\n'+ item_stdout
                      # if it's not a dict, just log the items
                      if (type(item)) != dict:
                        all_item_output = all_item_output +'\n'+item

                  if item_failed:
                    status='FAIL'
                  else:
                    status='PASS'

                  return all_item_output,status
                else:
                  if msg == 'All items completed':
                    status='PASS'
                    stdout = msg
                  elif msg == 'One or more items failed':
                    status='FAIL'
                    stdout = msg
                  elif msg != '':
                    # else it could be just a debug msg, so just display debug msg
                   # check if its a boolean, if so turn into string
                    if type(msg) == bool:
                      status = str(msg)
                    # N/A on any task which is not applicable
                    elif msg == "N/A":
                      status = 'N/A'
                    else:
                      status = 'FAIL'
                    stdout = str(msg)
                  else:
                    status=''
                    stdout=''
                  return stdout,status


    def on_any(self, *args, **kwargs):
        pass

    def runner_on_failed(self, host, res, ignore_errors=False):
        self.custom_reporter(res,host)
        # global pid
        # global pid_status
        # global pid_stack
        # global count_pid

        # if count_pid == 0 :
        #   count_pid += 1
        #   pid = self.taskid
        #   self.report.write("\n{0}, {1}, {2}".format(pid,count_pid,self.taskid))
        # else:
        #   if pid == self.taskid:
        #     count_pid += 1
        #     pid = self.taskid
        #   else:
        #     count_pid = 0
        #     pid = self.taskid
        #     self.report.write("\n{0}, {1}, {2}".format(pid,count_pid,self.taskid))
        
        # self.report.write("\n{0}, {1}, {2}".format(pid,count_pid,self.taskid))
        

    def runner_on_ok(self, host, res):
        self.custom_reporter(res,host)

        # global pid
        # global pid_status
        # global pid_stack
        # global count_pid

        # if count_pid == 0 :
        #   count_pid += 1
        #   pid = self.taskid
        #   self.report.write("\n{0}, {1}, {2}".format(pid,count_pid,self.taskid))
        # else:
        #   if pid == self.taskid:
        #     count_pid += 1
        #     pid = self.taskid
        #   else:
        #     count_pid = 0
        #     pid = self.taskid
        #     self.report.write("\n{0}, {1}, {2}".format(pid,count_pid,self.taskid))
            

        # self.report.write("\n{0}, {1}, {2}".format(pid,count_pid,self.taskid))


    def runner_on_error(self, host, msg):
        pass

    def runner_on_skipped(self, host, item=None):
        pass

    def runner_on_unreachable(self, host, res):
        self.custom_reporter(res,host)

    def runner_on_no_hosts(self):
        pass

    def runner_on_async_poll(self, host, res, jid, clock):
        self.custom_reporter(res,host)

    def runner_on_async_ok(self, host, res, jid):
        self.custom_reporter(res,host)

    def runner_on_async_failed(self, host, res, jid):
        self.custom_reporter(res,host)

    def playbook_on_start(self):
        self.create_logs()

    def playbook_on_notify(self, host, handler):
        pass

    def playbook_on_no_hosts_matched(self):
        pass

    def playbook_on_no_hosts_remaining(self):
        pass

    def playbook_on_task_start(self, name, is_conditional):
        self.setTaskID(name,is_conditional)

    def playbook_on_vars_prompt(self, varname, private=True, prompt=None,
                                encrypt=None, confirm=False, salt_size=None,
                                salt=None, default=None):
        pass

    def playbook_on_setup(self):
        pass

    def playbook_on_import_for_host(self, host, imported_file):
        pass

    def playbook_on_not_import_for_host(self, host, missing_file):
        pass

    def playbook_on_play_start(self, pattern):
        pass

    def playbook_on_stats(self, stats):
        pass