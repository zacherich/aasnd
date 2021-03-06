/**
 * Created by luforn on 2017-11-21.
 */

$(function(){

    var scanable = true; //是否可以继续扫描
    new VScanner(function(barcode) {
        if (barcode == null || barcode == '') {
            scanable = true;
            layer.msg('扫描条码异常！', {icon: 5});
            return;
        }
        var prefix = barcode.substring(0,2);
        if(prefix=='AM'){
            action_scan_employee(barcode);
        }else{
            action_scan_serialnumber(barcode);
        }
    });

    function action_scan_employee(barcode){
        if(!scanable){
            layer.msg('操作正在处理，请耐心等待！', {icon: 5});
            return ;
        }
        scanable = false;
        var scanparams = {'barcode': barcode};
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        $.ajax({
            url: '/aasmes/ipqcchecking/scanemployee',
            headers:{'Content-Type':'application/json'},
            type: 'post', timeout:10000, dataType: 'json',
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: scanparams, id: access_id}),
            success:function(data){
                scanable = true;
                var dresult = data.result;
                if(!dresult.success){
                    layer.msg(dresult.message, {icon: 5});
                    return ;
                }
                $('#mes_employee').attr('employeeid', dresult.employee_id).html(dresult.employee_name);
                localStorage.setItem('ipqc_employeeid', dresult.employee_id);
                localStorage.setItem('ipqc_employeename', dresult.employee_name);
            },
            error:function(xhr,type,errorThrown){
                scanable = true;
                console.log(type);
            }
        });
    }

    function action_scan_serialnumber(barcode){
        if(!scanable){
            layer.msg('操作正在处理，请耐心等待！', {icon: 5});
            return ;
        }
        scanable = false;
        var scanparams = {'barcode': barcode};
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        $.ajax({
            url: '/aasmes/ipqcchecking/scanserialnumber',
            headers:{'Content-Type':'application/json'},
            type: 'post', timeout:10000, dataType: 'json',
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: scanparams, id: access_id}),
            success:function(data){
                scanable = true;
                var dresult = data.result;
                if(!dresult.success){
                    layer.msg(dresult.message, {icon: 5});
                    return ;
                }
                $('#mes_serialnumber').html(dresult.serialnumber_name).attr('serialnumberid', dresult.serialnumber_id);
                $('#mes_customerpn').html(dresult.customerpn);
                $('#mes_internalpn').html(dresult.internalpn);
            },
            error:function(xhr,type,errorThrown){
                scanable = true;
                console.log(type);
            }
        });
    }

    $('#action_done').click(function(){
        var employeeid = parseInt($('#mes_employee').attr('employeeid'));
        if(employeeid==0){
            layer.msg('您还未添加IPQC质检员，请先添加IPQC质检员！', {icon: 5});
            return ;
        }
        var serialnumberid = parseInt($('#mes_serialnumber').attr('serialnumberid'));
        if(serialnumberid==0){
            layer.msg('您还未扫描成品条码，请先扫描成品条码！', {icon: 5});
            return ;
        }
        var checkresult = $('#mes_result').val();
        if(checkresult==null || checkresult==''){
           checkresult = 'ok';
        }
        var scanparams = {'serialnumberid': serialnumberid, 'ipqccheckerid': employeeid, 'checkresult': checkresult};
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        $.ajax({
            url: '/aasmes/ipqcchecking/actiondone',
            headers:{'Content-Type':'application/json'},
            type: 'post', timeout:10000, dataType: 'json',
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: scanparams, id: access_id}),
            success:function(data){
                scanable = true;
                var dresult = data.result;
                if(!dresult.success){
                    layer.msg(dresult.message, {icon: 5});
                    return ;
                }
                window.location.reload(true);
            },
            error:function(xhr,type,errorThrown){
                scanable = true;
                console.log(type);
            }
        });
    });

    //清理员工信息
    $('#action_clearemployee').click(function(){
        layer.confirm('您确定清理员工信息？', {'btn': ['确定', '取消']}, function(index){
            layer.close(index);
            $('#mes_employee').attr('employeeid', '0').html('');
            localStorage.setItem('ipqc_employeeid', '0');
            localStorage.setItem('ipqc_employeename', '');
        },function(){});
    });


    var employeeid = localStorage.getItem('ipqc_employeeid');
    var employeename = localStorage.getItem('ipqc_employeename');
    if(employeeid!=null && employeeid!='0'){
       $('#mes_employee').attr('employeeid', employeeid).html(employeename);
    }

});
