"""
EII — Knowledge Base
Pure eSocial government integration incidents.
No HCM system references — only government webservice errors.
"""

KB = [
    # ──────────────────────────────────────────────────────
    # ERROS DE RETIFICAÇÃO
    # ──────────────────────────────────────────────────────
    {
        "id": "KB001",
        "evento": "S-1200",
        "codigo_erro": "E428",
        "titulo": "Campo indRetif deve ser 2 em retificação",
        "descricao": "Evento S-1200 rejeitado com E428 ao reenviar. O campo indRetif está como 1 (original) mas o campo nrRecEvt foi preenchido com o recibo do evento anterior, indicando intenção de retificação.",
        "causa_raiz": "Conflito entre indRetif=1 (novo evento) e nrRecEvt preenchido (retificação). Quando nrRecEvt é informado, obrigatoriamente indRetif deve ser 2. A regra de negócio do eSocial é: retificação exige ambos os campos consistentes.",
        "passos_resolucao": [
            "Identificar o número do recibo original (nrRec) do evento S-1200 que se deseja retificar na plataforma eSocial",
            "No XML de retransmissão, definir indRetif=2",
            "Preencher nrRecEvt com o nrRec do evento original que está sendo corrigido",
            "Reprocessar o lote com o XML corrigido",
            "Confirmar aceite na plataforma eSocial — o evento retificado aparece com status 'Retificado'"
        ],
        "validacao": "Consultar o evento original na plataforma eSocial e verificar que seu status mudou para 'Retificado'. O evento de retificação deve estar com cdResposta=201.",
        "tempo_estimado": "1-2h",
        "impacto": "alto",
        "tags": ["S-1200", "E428", "indRetif", "retificação", "nrRecEvt", "remuneração"]
    },
    {
        "id": "KB002",
        "evento": "S-3000",
        "codigo_erro": "E430",
        "titulo": "Exclusão S-3000 com nrRec inválido ou já excluído",
        "descricao": "Evento S-3000 (Exclusão de Eventos) rejeitado com E430. O número do recibo (nrRec) informado para exclusão não existe na base do eSocial ou o evento já foi excluído anteriormente.",
        "causa_raiz": "O nrRec informado no S-3000 pode estar: digitado incorretamente, pertencer a outro CNPJ/CPF, já ter sido excluído por outro S-3000, ou o evento original nunca ter sido processado com sucesso.",
        "passos_resolucao": [
            "Acessar a plataforma eSocial e localizar o evento pelo nrRec para verificar sua situação atual",
            "Confirmar que o nrRec pertence ao mesmo CNPJ transmissor",
            "Verificar se já existe um S-3000 processado para esse nrRec",
            "Se o evento original ainda está ativo, corrigir o nrRec no XML do S-3000 e retransmitir",
            "Se já foi excluído, nenhuma ação adicional é necessária"
        ],
        "validacao": "Consultar o evento original na plataforma pelo nrRec e confirmar status 'Excluído' após processamento do S-3000.",
        "tempo_estimado": "1h",
        "impacto": "médio",
        "tags": ["S-3000", "E430", "exclusão", "nrRec", "nrRecEvt"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE CERTIFICADO E ASSINATURA
    # ──────────────────────────────────────────────────────
    {
        "id": "KB003",
        "evento": "Qualquer",
        "codigo_erro": "E214",
        "titulo": "Certificado digital expirado — rejeição em massa",
        "descricao": "Todos os eventos do lote rejeitados com E214. Erro de assinatura digital inválida. Ocorre quando o certificado A1 ou A3 utilizado para assinar os XMLs atingiu a data de validade ou foi revogado pela ICP-Brasil.",
        "causa_raiz": "O certificado digital ICP-Brasil (A1 ou A3) utilizado para assinar os XMLs antes da transmissão expirou. O webservice do eSocial valida o certificado em cada transmissão e rejeita qualquer XML assinado com certificado fora da validade ou com cadeia de certificação inválida.",
        "passos_resolucao": [
            "URGENTE: Identificar a autoridade certificadora (AC) que emitiu o certificado atual",
            "Solicitar renovação do certificado digital junto à AC (ex: Serasa, Certisign, Valid, Soluti)",
            "Instalar o novo certificado no servidor ou estação que realiza a transmissão",
            "Atualizar a configuração do middleware/software de transmissão com o novo certificado",
            "Realizar transmissão de teste com evento não crítico antes de reprocessar o lote completo",
            "Reprocessar todos os eventos rejeitados após confirmar que o novo certificado está funcionando",
            "Configurar alerta de vencimento 60 dias antes da expiração para evitar recorrência"
        ],
        "validacao": "Transmitir um evento de consulta e verificar aceite sem erro E214. Confirmar data de validade do novo certificado no middleware.",
        "tempo_estimado": "4-8h (depende da AC e processo de emissão)",
        "impacto": "crítico",
        "tags": ["E214", "certificado digital", "A1", "A3", "ICP-Brasil", "assinatura", "expirado", "revogado", "rejeição em massa"]
    },
    {
        "id": "KB004",
        "evento": "Qualquer",
        "codigo_erro": "E215",
        "titulo": "CNPJ do transmissor não autorizado a transmitir para o empregador",
        "descricao": "Rejeição E215: o CNPJ que assinou e transmitiu o lote não está autorizado como transmissor para o empregador informado no ideEmpregador.",
        "causa_raiz": "O eSocial exige que o CNPJ transmissor esteja previamente autorizado pelo empregador no Portal eSocial. Se o escritório contábil ou prestador de serviços mudou de CNPJ ou ainda não foi cadastrado, todos os envios serão rejeitados.",
        "passos_resolucao": [
            "Acessar o Portal eSocial com certificado do empregador (não do transmissor)",
            "Navegar até Empresas > Procurações e Autorizações",
            "Verificar se o CNPJ do transmissor atual está na lista de autorizados",
            "Se não estiver: adicionar o CNPJ do novo transmissor e salvar",
            "Aguardar propagação (pode levar até 24h) e retransmitir o lote"
        ],
        "validacao": "Retransmitir lote de teste e confirmar aceite sem E215.",
        "tempo_estimado": "2-4h",
        "impacto": "crítico",
        "tags": ["E215", "transmissor", "autorização", "procuração", "CNPJ", "portal eSocial"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE VÍNCULO / ADMISSÃO / DESLIGAMENTO
    # ──────────────────────────────────────────────────────
    {
        "id": "KB005",
        "evento": "S-2200",
        "codigo_erro": "E469",
        "titulo": "CNPJ do estabelecimento inativo ou inexistente na RFB",
        "descricao": "S-2200 rejeitado com E469. O CNPJ informado no campo ideEmpregador ou no vínculo não consta na base da Receita Federal como ativo.",
        "causa_raiz": "O campo nrInsc do empregador está preenchido com um CNPJ que: foi baixado/cancelado na RFB, está inapto, pertence à matriz mas o vínculo é com uma filial que tem CNPJ próprio, ou foi digitado com erro.",
        "passos_resolucao": [
            "Consultar a situação cadastral do CNPJ no portal da RFB: https://servicos.receita.fazenda.gov.br/servicos/cnpjreva/Cnpjreva_Solicitacao.asp",
            "Se CNPJ inapto/cancelado: regularizar a situação na RFB antes de qualquer envio",
            "Se CNPJ da matriz no lugar da filial: identificar o CNPJ correto da filial e corrigir no XML",
            "Se erro de digitação: corrigir o nrInsc no XML",
            "Retransmitir o S-2200 com o CNPJ correto e ativo"
        ],
        "validacao": "Consultar CNPJ na RFB para confirmar situação ativa antes de retransmitir. Confirmar aceite do S-2200 na plataforma.",
        "tempo_estimado": "2-3h (regularização pode levar dias se CNPJ irregular)",
        "impacto": "alto",
        "tags": ["S-2200", "E469", "CNPJ", "RFB", "estabelecimento", "filial", "inativo", "admissão"]
    },
    {
        "id": "KB006",
        "evento": "S-2299",
        "codigo_erro": "E312",
        "titulo": "Desligamento sem vínculo ativo no eSocial",
        "descricao": "S-2299 (Desligamento) rejeitado com E312. O eSocial não encontra vínculo empregatício ativo para o CPF e CNPJ informados.",
        "causa_raiz": "O evento S-2200 (admissão) nunca foi enviado ou foi rejeitado/excluído. Isso ocorre frequentemente com funcionários admitidos antes da implantação do eSocial na empresa, quando o evento inicial não foi transmitido.",
        "passos_resolucao": [
            "Consultar o CPF do trabalhador na plataforma eSocial para verificar se existe algum vínculo registrado",
            "Se nenhum vínculo existir: enviar S-2200 retroativo com a data de admissão original do funcionário",
            "Aguardar processamento e confirmação do S-2200 (pode levar até 24h)",
            "Após confirmação do vínculo ativo, reenviar o S-2299 com a data de desligamento correta",
            "Verificar se há outros eventos pendentes para o mesmo trabalhador (S-1200, S-2230, etc.)"
        ],
        "validacao": "Confirmar vínculo ativo na consulta da plataforma eSocial antes de reenviar S-2299. Após envio do desligamento, confirmar recibo de processamento.",
        "tempo_estimado": "4-8h",
        "impacto": "alto",
        "tags": ["S-2299", "E312", "desligamento", "vínculo", "S-2200", "admissão retroativa"]
    },
    {
        "id": "KB007",
        "evento": "S-2206",
        "codigo_erro": "E422",
        "titulo": "Alteração contratual sem vínculo base no eSocial",
        "descricao": "S-2206 (Alteração de Contrato de Trabalho) rejeitado com E422. O eSocial não localiza um S-2200 ativo correspondente ao vínculo que se deseja alterar.",
        "causa_raiz": "O vínculo base não existe na plataforma porque: o S-2200 foi excluído indevidamente via S-3000, o S-2200 está em status de erro na plataforma, o CPF informado no S-2206 diverge do CPF no S-2200 original, ou o empregador trocou de CNPJ sem reenviar os vínculos.",
        "passos_resolucao": [
            "Consultar a situação do vínculo na plataforma eSocial usando o CPF do trabalhador",
            "Verificar histórico de S-3000 (exclusões) para o CPF — pode ter sido excluído indevidamente",
            "Se o vínculo foi excluído: reenviar o S-2200 original com todos os dados corretos",
            "Se há divergência de CPF: verificar qual CPF consta no S-2200 original e usar o mesmo no S-2206",
            "Após confirmação do vínculo ativo, reenviar o S-2206"
        ],
        "validacao": "Consultar vínculo ativo na plataforma e confirmar S-2206 processado com cdResposta=201.",
        "tempo_estimado": "3-4h",
        "impacto": "alto",
        "tags": ["S-2206", "E422", "alteração contratual", "vínculo", "S-2200", "S-3000"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE REMUNERAÇÃO / FOLHA
    # ──────────────────────────────────────────────────────
    {
        "id": "KB008",
        "evento": "S-1210",
        "codigo_erro": "E301",
        "titulo": "CPF do trabalhador divergente entre S-1200 e S-1210",
        "descricao": "S-1210 rejeitado com E301. O CPF do trabalhador no S-1210 não coincide com o CPF informado no S-1200 do mesmo período de apuração.",
        "causa_raiz": "O CPF foi corrigido após o envio do S-1200. O S-1210 está usando o CPF atual (correto) enquanto o S-1200 foi processado com o CPF anterior. O eSocial valida consistência de CPF entre os eventos relacionados do mesmo período.",
        "passos_resolucao": [
            "Identificar o CPF que foi usado no S-1200 original já processado pelo eSocial",
            "Enviar S-3000 para excluir o S-1200 com CPF incorreto (usar o nrRec do S-1200 original)",
            "Aguardar confirmação da exclusão",
            "Reenviar S-1200 com o CPF correto (indRetif=1, novo evento)",
            "Aguardar processamento do novo S-1200",
            "Reenviar o S-1210 após confirmação do S-1200 correto"
        ],
        "validacao": "Consultar S-1200 e S-1210 na plataforma — ambos devem constar com o mesmo CPF e cdResposta=201.",
        "tempo_estimado": "2-4h",
        "impacto": "alto",
        "tags": ["S-1210", "S-1200", "E301", "CPF", "divergência", "pagamento", "remuneração"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE TRANSMISSÃO / LOTE
    # ──────────────────────────────────────────────────────
    {
        "id": "KB009",
        "evento": "Qualquer",
        "codigo_erro": "E500",
        "titulo": "Timeout por volume excessivo no lote",
        "descricao": "Erro E500 (timeout) na transmissão de lote. O webservice do governo retorna erro de timeout quando o lote excede o limite de 50 eventos ou quando o ambiente está sobrecarregado.",
        "causa_raiz": "O lote foi montado com mais de 50 eventos, ultrapassando o limite do webservice do eSocial. Também pode ocorrer em períodos de alta demanda (datas de fechamento de folha, datas limite de eSocial) mesmo com lotes menores.",
        "passos_resolucao": [
            "Verificar o status do ambiente eSocial em: https://servicos.receita.fazenda.gov.br",
            "Redimensionar os lotes para no máximo 50 eventos cada",
            "Para folhas grandes: dividir por grupo de trabalhadores (ex: lotes de 20-30 eventos)",
            "Implementar retry automático com backoff exponencial: aguardar 5min, 15min, 30min entre tentativas",
            "Agendar retransmissão para horários de menor demanda (madrugada ou início da manhã)",
            "Monitorar a fila de transmissão após reenvio"
        ],
        "validacao": "Confirmar todos os eventos processados com cdResposta=201 na plataforma eSocial.",
        "tempo_estimado": "2-3h",
        "impacto": "médio",
        "tags": ["E500", "timeout", "lote", "volume", "50 eventos", "webservice", "transmissão"]
    },
    {
        "id": "KB010",
        "evento": "Qualquer",
        "codigo_erro": "401",
        "titulo": "cdResposta 401 — Lote rejeitado por inconsistência de schema",
        "descricao": "Lote rejeitado com cdResposta=401 sem código de erro específico. Indica que o XML não está em conformidade com o schema XSD do eSocial para o evento transmitido.",
        "causa_raiz": "O XML gerado não passou na validação de schema. Causas comuns: versão do schema desatualizada, campos obrigatórios ausentes, tipos de dados incorretos (data no formato errado, valor numérico com formatação inválida), ou estrutura de tags fora de ordem.",
        "passos_resolucao": [
            "Baixar o schema XSD atualizado do evento no portal eSocial: https://www.gov.br/esocial/pt-br/documentacao-tecnica",
            "Validar o XML gerado contra o schema XSD com uma ferramenta como XMLSpy, Oxygen, ou validador online",
            "Identificar os campos com erro de validação de schema",
            "Corrigir o XML e retransmitir",
            "Verificar se o software de geração XML está usando a versão mais recente do leiaute"
        ],
        "validacao": "Validar XML contra schema XSD antes de transmitir. Após transmissão, confirmar cdResposta=201.",
        "tempo_estimado": "2-4h",
        "impacto": "alto",
        "tags": ["401", "schema", "XSD", "validação", "XML", "leiaute", "inconsistência"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE AFASTAMENTO / FÉRIAS
    # ──────────────────────────────────────────────────────
    {
        "id": "KB011",
        "evento": "S-2230",
        "codigo_erro": "E350",
        "titulo": "Afastamento S-2230 com data anterior ao vínculo ativo",
        "descricao": "S-2230 (Afastamento Temporário) rejeitado com E350. A data de início do afastamento é anterior à data de admissão registrada no S-2200 do trabalhador.",
        "causa_raiz": "A data de admissão no eSocial (S-2200) diverge da data real de admissão do trabalhador, ou o S-2230 foi preenchido com data incorreta. O eSocial valida que o afastamento só pode iniciar após a data de admissão registrada.",
        "passos_resolucao": [
            "Consultar a data de admissão registrada no S-2200 na plataforma eSocial",
            "Verificar se a data de admissão no S-2200 está correta — se não estiver, retificar o S-2200 primeiro",
            "Corrigir a data de início do afastamento no S-2230 para ser posterior à data de admissão",
            "Retransmitir o S-2230 com a data corrigida"
        ],
        "validacao": "Confirmar S-2230 processado com cdResposta=201 e data de afastamento coerente com o histórico.",
        "tempo_estimado": "2h",
        "impacto": "médio",
        "tags": ["S-2230", "E350", "afastamento", "data admissão", "vínculo", "S-2200"]
    },
    {
        "id": "KB012",
        "evento": "S-2230",
        "codigo_erro": "E351",
        "titulo": "Afastamento S-2230 com período sobreposto a afastamento anterior",
        "descricao": "S-2230 rejeitado com E351. Já existe um afastamento ativo ou com período sobreposto para o mesmo trabalhador na plataforma.",
        "causa_raiz": "Um S-2230 anterior com datas que cobrem total ou parcialmente o mesmo período ainda está ativo no eSocial. Pode ter sido enviado em duplicata ou o retorno do afastamento (S-2230 com dtFimAfast) não foi transmitido.",
        "passos_resolucao": [
            "Consultar todos os afastamentos do trabalhador na plataforma eSocial",
            "Identificar o afastamento sobreposto e seu nrRec",
            "Se duplicata: enviar S-3000 para excluir o afastamento duplicado",
            "Se o retorno do afastamento anterior não foi enviado: enviar S-2230 com dtFimAfast para encerrar o período anterior",
            "Após encerramento, retransmitir o novo S-2230"
        ],
        "validacao": "Verificar no histórico de afastamentos da plataforma que não há sobreposição de períodos antes de retransmitir.",
        "tempo_estimado": "2-3h",
        "impacto": "médio",
        "tags": ["S-2230", "E351", "afastamento", "sobreposição", "duplicata", "período"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE TABELAS E EVENTOS INICIAIS
    # ──────────────────────────────────────────────────────
    {
        "id": "KB013",
        "evento": "S-1000",
        "codigo_erro": "E100",
        "titulo": "S-1000 rejeitado — empregador já cadastrado",
        "descricao": "S-1000 (Informações do Empregador) rejeitado com E100. O empregador já possui cadastro ativo no eSocial e um novo S-1000 não pode ser enviado sem retificar o existente.",
        "causa_raiz": "O S-1000 é enviado com indRetif=1 (novo) mas já existe um S-1000 processado para esse CNPJ. Para atualizar informações do empregador, deve-se enviar o S-1000 com indRetif=2 e o nrRecEvt do evento original.",
        "passos_resolucao": [
            "Consultar o S-1000 existente na plataforma e copiar o nrRec",
            "Alterar no XML: indRetif=2 e preencher nrRecEvt com o nrRec do S-1000 original",
            "Corrigir os campos que precisam ser atualizados",
            "Retransmitir como retificação"
        ],
        "validacao": "Confirmar S-1000 com indRetif=2 processado e dados do empregador atualizados na plataforma.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1000", "E100", "empregador", "duplicata", "indRetif", "cadastro"]
    },
    {
        "id": "KB014",
        "evento": "S-1070",
        "codigo_erro": "E601",
        "titulo": "Processo judicial S-1070 com data de decisão futura",
        "descricao": "S-1070 (Tabela de Processos Administrativos/Judiciais) rejeitado com E601. A data de decisão informada é posterior à data atual de transmissão.",
        "causa_raiz": "Erro de preenchimento: o campo dtDecisao foi preenchido com data futura (erro de digitação no ano, por exemplo, 2025 em vez de 2024). O eSocial valida que a data da decisão judicial não pode ser futura.",
        "passos_resolucao": [
            "Verificar a data correta da decisão no documento judicial físico",
            "Corrigir o campo dtDecisao no XML com a data real da decisão",
            "Reenviar o S-1070 com a data corrigida",
            "Implementar validação de data no formulário de cadastro para evitar recorrência"
        ],
        "validacao": "Confirmar S-1070 processado com data de decisão correta e cdResposta=201.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1070", "E601", "processo judicial", "data decisão", "dtDecisao"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE COMPETÊNCIA / PERÍODO
    # ──────────────────────────────────────────────────────
    {
        "id": "KB015",
        "evento": "S-1200",
        "codigo_erro": "E320",
        "titulo": "Competência S-1200 encerrada — prazo expirado",
        "descricao": "S-1200 rejeitado com E320. O período de apuração (perApur) informado no evento corresponde a uma competência cujo prazo de transmissão já encerrou no eSocial.",
        "causa_raiz": "O eSocial tem prazo definido para transmissão de eventos periódicos. A competência informada está fora da janela de transmissão permitida. Isso ocorre quando há atraso no envio ou quando se tenta enviar competências muito antigas.",
        "passos_resolucao": [
            "Verificar o calendário de obrigações do eSocial para identificar os prazos vigentes",
            "Para competências atrasadas: verificar se ainda há possibilidade de transmissão extemporânea",
            "Contatar o e-CAC da RFB para orientação sobre retificações fora do prazo",
            "Em casos de autuação: verificar programa de regularização espontânea (PERT, parcelamento)",
            "Implementar calendário de alertas para evitar recorrência"
        ],
        "validacao": "Confirmar com a RFB a possibilidade de transmissão extemporânea antes de tentar reenvio.",
        "tempo_estimado": "Variável — pode exigir contato com RFB",
        "impacto": "crítico",
        "tags": ["S-1200", "E320", "competência", "prazo", "perApur", "extemporâneo", "remuneração", "dtFecEvt"]
    },
    {
        "id": "KB016",
        "evento": "S-1299",
        "codigo_erro": "E450",
        "titulo": "Fechamento S-1299 sem todos os eventos periódicos da competência",
        "descricao": "S-1299 (Fechamento dos Eventos Periódicos) rejeitado com E450. Há eventos periódicos pendentes (S-1200, S-1210, etc.) para a competência que ainda não foram transmitidos ou estão em erro.",
        "causa_raiz": "O S-1299 sinaliza o encerramento da competência. O eSocial valida que todos os trabalhadores com vínculo ativo têm S-1200 transmitido. Se algum trabalhador ativo não tem S-1200 para a competência, ou se há S-1200 com erro pendente, o S-1299 é rejeitado.",
        "passos_resolucao": [
            "Consultar na plataforma eSocial quais trabalhadores estão sem S-1200 para a competência",
            "Identificar e corrigir os S-1200 com erro pendente para a competência",
            "Enviar os S-1200 faltantes",
            "Aguardar processamento de todos os eventos periódicos",
            "Retransmitir o S-1299 somente após confirmação de todos os S-1200 processados"
        ],
        "validacao": "Verificar na plataforma que não há pendências de eventos periódicos antes de reenviar S-1299.",
        "tempo_estimado": "4-8h",
        "impacto": "alto",
        "tags": ["S-1299", "E450", "fechamento", "competência", "S-1200", "periódicos", "pendências"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE DADOS DO TRABALHADOR
    # ──────────────────────────────────────────────────────
    {
        "id": "KB017",
        "evento": "S-2200",
        "codigo_erro": "E460",
        "titulo": "CPF do trabalhador inválido ou não consta na base da RFB",
        "descricao": "S-2200 rejeitado com E460. O CPF informado no evento de admissão não está cadastrado na base de dados da Receita Federal ou está em situação irregular.",
        "causa_raiz": "O CPF pode estar: com erro de digitação, pertencer a um trabalhador estrangeiro não cadastrado na RFB, ter sido cancelado, ou estar em situação 'Pendente de Regularização' na RFB. O eSocial valida o CPF em tempo real contra a base da RFB.",
        "passos_resolucao": [
            "Consultar a situação do CPF na RFB: https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp",
            "Se CPF com erro de digitação: corrigir o número e reenviar o S-2200",
            "Se CPF irregular/pendente: o trabalhador deve regularizar o CPF junto à RFB antes da admissão",
            "Para trabalhadores estrangeiros: verificar processo de inscrição no CPF via consulado ou RFB",
            "Após regularização do CPF, retransmitir o S-2200"
        ],
        "validacao": "Consultar CPF na RFB e confirmar situação 'Regular' antes de retransmitir.",
        "tempo_estimado": "Variável — depende do processo de regularização do trabalhador",
        "impacto": "alto",
        "tags": ["S-2200", "E460", "CPF", "RFB", "trabalhador", "admissão", "irregular", "estrangeiro"]
    },
    {
        "id": "KB018",
        "evento": "S-2210",
        "codigo_erro": "E380",
        "titulo": "CAT S-2210 com CID incompatível com tipo de acidente",
        "descricao": "S-2210 (Comunicação de Acidente de Trabalho) rejeitado com E380. O código CID informado não é compatível com o tipo de acidente declarado (tpAcid).",
        "causa_raiz": "O eSocial valida a coerência entre o CID informado e o tipo de acidente. Por exemplo: CID relacionado a doença ocupacional enviado como acidente típico (tpAcid=1), ou CID de doença aguda enviado como doença do trabalho.",
        "passos_resolucao": [
            "Revisar o prontuário médico e o atestado do médico assistente para confirmar o CID correto",
            "Verificar a tabela de compatibilidade CID x tpAcid na documentação técnica do eSocial",
            "Corrigir o tpAcid ou o CID conforme o diagnóstico médico real",
            "Retransmitir o S-2210 com os dados corrigidos",
            "Se necessário, consultar o SESMT ou médico do trabalho para confirmação"
        ],
        "validacao": "Confirmar S-2210 processado e CAT registrada no INSS com os dados corretos.",
        "tempo_estimado": "2-3h",
        "impacto": "alto",
        "tags": ["S-2210", "E380", "CAT", "CID", "acidente trabalho", "tpAcid", "INSS"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE AMBIENTE / CONFIGURAÇÃO
    # ──────────────────────────────────────────────────────
    {
        "id": "KB019",
        "evento": "Qualquer",
        "codigo_erro": "E200",
        "titulo": "Evento enviado para ambiente errado (produção vs. homologação)",
        "descricao": "Evento rejeitado com E200. O valor do campo tpAmb (tipo de ambiente) não corresponde ao endpoint de transmissão utilizado. Evento de produção enviado para homologação ou vice-versa.",
        "causa_raiz": "O campo tpAmb no XML está como 1 (produção) mas o endpoint de transmissão é o de homologação (ou o contrário). Também ocorre quando a configuração do middleware é alterada sem atualizar o campo no XML.",
        "passos_resolucao": [
            "Verificar o endpoint de transmissão configurado no middleware: produção ou homologação",
            "Verificar o valor de tpAmb no XML: 1=Produção, 2=Homologação",
            "Alinhar o tpAmb com o endpoint correto",
            "Se estava em homologação inadvertidamente: confirmar que nenhum dado real foi comprometido",
            "Retransmitir com tpAmb e endpoint corretos"
        ],
        "validacao": "Confirmar que tpAmb=1 está sendo enviado para o endpoint de produção e tpAmb=2 para homologação.",
        "tempo_estimado": "1h",
        "impacto": "médio",
        "tags": ["E200", "tpAmb", "ambiente", "produção", "homologação", "endpoint", "configuração"]
    },
    {
        "id": "KB020",
        "evento": "Qualquer",
        "codigo_erro": "E403",
        "titulo": "Versão do leiaute descontinuada",
        "descricao": "Eventos rejeitados com E403. A versão do schema XML (versaoLeiaute) utilizada foi descontinuada pelo governo. O eSocial aceita apenas as versões vigentes do leiaute.",
        "causa_raiz": "O governo periodicamente descontinua versões antigas do leiaute do eSocial. O software de geração XML ainda está usando uma versão que foi depreciada, gerando eventos com namespace ou versaoLeiaute inválido.",
        "passos_resolucao": [
            "Consultar a versão vigente do leiaute em: https://www.gov.br/esocial/pt-br/documentacao-tecnica",
            "Verificar a versão atual do software/middleware de geração XML",
            "Atualizar o software para a versão compatível com o leiaute vigente",
            "Validar os XMLs gerados com o schema XSD da versão correta",
            "Retransmitir após atualização e validação"
        ],
        "validacao": "Transmitir evento de teste e confirmar aceite. Verificar que versaoLeiaute está alinhado com a documentação atual.",
        "tempo_estimado": "4-8h (atualização de software pode exigir fornecedor)",
        "impacto": "crítico",
        "tags": ["E403", "leiaute", "versão", "schema", "namespace", "descontinuado", "atualização"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO A — S-1005: TABELA DE ESTABELECIMENTOS
    # ──────────────────────────────────────────────────────
    {
        "id": "KB021",
        "evento": "S-1005",
        "codigo_erro": "E100",
        "titulo": "Estabelecimento S-1005 já cadastrado — usar retificação",
        "descricao": "S-1005 (Tabela de Estabelecimentos) rejeitado com E100. O estabelecimento identificado pelo CNPJ já possui cadastro ativo no eSocial e não pode ser enviado novamente como evento original (indRetif=1).",
        "causa_raiz": "O eSocial rejeita eventos de tabela duplicados. Quando o estabelecimento já foi cadastrado via S-1005 anterior, qualquer atualização deve ser feita com indRetif=2 (retificação) referenciando o nrRec do evento original. Enviar um novo S-1005 com indRetif=1 para um CNPJ já existente resulta em E100.",
        "passos_resolucao": [
            "Consultar o S-1005 existente na plataforma eSocial e localizar o nrRec do evento original",
            "Alterar o XML do novo S-1005: definir indRetif=2",
            "Preencher o campo nrRecEvt com o nrRec do S-1005 original",
            "Atualizar apenas os campos que precisam ser corrigidos ou atualizados",
            "Retransmitir o S-1005 como retificação",
            "Confirmar processamento com cdResposta=201 na plataforma"
        ],
        "validacao": "Consultar o estabelecimento na plataforma eSocial e verificar que os dados atualizados estão refletidos. O S-1005 retificado deve aparecer com cdResposta=201.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1005", "E100", "estabelecimento", "duplicata", "indRetif", "retificação", "tabela"]
    },
    {
        "id": "KB022",
        "evento": "S-1005",
        "codigo_erro": "E469",
        "titulo": "CNPJ do estabelecimento inativo ou inexistente na RFB",
        "descricao": "S-1005 rejeitado com E469. O CNPJ informado para o estabelecimento não consta na base da Receita Federal como ativo, está cancelado, inapto, ou foi digitado com erro.",
        "causa_raiz": "O eSocial valida em tempo real a situação cadastral do CNPJ de cada estabelecimento na RFB antes de aceitar o S-1005. CNPJs baixados, inaptos ou com irregularidade na RFB são recusados. Filiais com CNPJ próprio mas incorretamente informadas com o CNPJ da matriz também geram E469.",
        "passos_resolucao": [
            "Consultar a situação cadastral do CNPJ em: https://servicos.receita.fazenda.gov.br/servicos/cnpjreva/Cnpjreva_Solicitacao.asp",
            "Se CNPJ inapto ou cancelado: providenciar regularização na RFB antes de qualquer envio ao eSocial",
            "Se CNPJ de filial incorreto: identificar e usar o CNPJ específico da filial, não da matriz",
            "Se erro de digitação: corrigir o nrInsc do estabelecimento no XML",
            "Retransmitir o S-1005 somente após confirmar situação 'Ativa' na RFB"
        ],
        "validacao": "Verificar situação 'Ativa' do CNPJ na RFB antes de retransmitir. Após envio, confirmar aceite do S-1005 com cdResposta=201.",
        "tempo_estimado": "2-3h (regularização pode levar dias se CNPJ irregular)",
        "impacto": "alto",
        "tags": ["S-1005", "E469", "CNPJ", "RFB", "estabelecimento", "filial", "inativo", "tabela"]
    },
    {
        "id": "KB023",
        "evento": "S-1005",
        "codigo_erro": "E136",
        "titulo": "CNAE inválido para o tipo de estabelecimento",
        "descricao": "S-1005 rejeitado com E136. O código CNAE (Classificação Nacional de Atividades Econômicas) informado para o estabelecimento é inválido, inexistente na tabela vigente, ou incompatível com o tipo de inscrição do empregador.",
        "causa_raiz": "O eSocial valida o CNAE contra a tabela oficial do IBGE. CNAEs desativados em revisões anteriores da tabela, CNAEs informados sem o dígito verificador correto, ou CNAEs incompatíveis com a natureza jurídica do empregador (ex.: atividade privada para órgão público) geram E136.",
        "passos_resolucao": [
            "Consultar a tabela vigente de CNAEs no portal do IBGE: https://cnae.ibge.gov.br",
            "Verificar se o CNAE informado está ativo e corresponde à atividade principal do estabelecimento",
            "Consultar o CNPJ na RFB para confirmar o CNAE cadastrado oficialmente para o estabelecimento",
            "Corrigir o campo CNAE no XML do S-1005 com o código vigente",
            "Retransmitir o S-1005 com o CNAE correto"
        ],
        "validacao": "Confirmar que o CNAE informado consta como ativo na tabela IBGE e corresponde ao CNAE do CNPJ na RFB. S-1005 deve ser processado com cdResposta=201.",
        "tempo_estimado": "1-2h",
        "impacto": "médio",
        "tags": ["S-1005", "E136", "CNAE", "IBGE", "estabelecimento", "atividade econômica", "tabela"]
    },
    {
        "id": "KB024",
        "evento": "S-1005",
        "codigo_erro": "E138",
        "titulo": "CEP do endereço do estabelecimento não localizado",
        "descricao": "S-1005 rejeitado com E138. O CEP informado no endereço do estabelecimento não foi localizado na base dos Correios ou está em formato inválido.",
        "causa_raiz": "O eSocial valida o CEP informado no S-1005 contra a base de endereçamento dos Correios. CEPs digitados com erro, CEPs de logradouros extintos, ou CEPs fora do padrão de 8 dígitos resultam em E138. Também ocorre quando o CEP é correto mas foi atribuído recentemente e ainda não está na base do eSocial.",
        "passos_resolucao": [
            "Consultar o CEP correto no portal dos Correios: https://buscacepinter.correios.com.br",
            "Verificar se o endereço do estabelecimento está atualizado no cartão CNPJ da RFB",
            "Corrigir o CEP no XML do S-1005 com o código vigente (8 dígitos sem hífen)",
            "Se o CEP for recente: aguardar atualização da base do eSocial (até 30 dias) ou usar o CEP geral do município",
            "Retransmitir o S-1005 com o CEP correto"
        ],
        "validacao": "Confirmar CEP válido no portal dos Correios antes de retransmitir. S-1005 deve ser aceito com cdResposta=201.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1005", "E138", "CEP", "endereço", "Correios", "estabelecimento", "tabela"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO B — S-1010 / S-1020: RUBRICAS E LOTAÇÕES
    # ──────────────────────────────────────────────────────
    {
        "id": "KB025",
        "evento": "S-1010",
        "codigo_erro": "E100",
        "titulo": "Rubrica S-1010 já cadastrada — usar retificação",
        "descricao": "S-1010 (Tabela de Rubricas da Folha de Pagamento) rejeitado com E100. A rubrica identificada pelo código já existe na tabela do empregador no eSocial e não pode ser cadastrada novamente como evento original.",
        "causa_raiz": "A rubrica foi enviada anteriormente com sucesso. Para alterar descrição, natureza, ou incidências de uma rubrica existente, é obrigatório usar indRetif=2 (retificação) com referência ao nrRec do S-1010 original. Enviar novo S-1010 com o mesmo código de rubrica e indRetif=1 gera E100.",
        "passos_resolucao": [
            "Localizar na plataforma eSocial o S-1010 existente para a rubrica e copiar o nrRec",
            "No XML do novo S-1010, definir indRetif=2 e preencher nrRecEvt com o nrRec original",
            "Atualizar apenas os campos que necessitam correção",
            "Retransmitir o S-1010 como retificação",
            "Confirmar processamento na plataforma"
        ],
        "validacao": "Consultar a rubrica na tabela do empregador na plataforma e confirmar que as alterações foram aplicadas. S-1010 com cdResposta=201.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1010", "E100", "rubrica", "folha pagamento", "indRetif", "retificação", "tabela"]
    },
    {
        "id": "KB026",
        "evento": "S-1010",
        "codigo_erro": "E602",
        "titulo": "Natureza da rubrica incompatível com o código de incidência",
        "descricao": "S-1010 rejeitado com E602. A natureza (tpRubr) da rubrica informada é incompatível com os códigos de incidência previdenciária, IRRF ou FGTS declarados para ela.",
        "causa_raiz": "O eSocial valida a coerência entre a natureza da rubrica (proventos, descontos, informativas) e os códigos de incidência. Por exemplo: uma rubrica de desconto (tpRubr=2) não pode ter incidência de FGTS como base de cálculo; ou uma rubrica informativa (tpRubr=4) não pode ter incidências tributárias ativas.",
        "passos_resolucao": [
            "Consultar a tabela de natureza de rubricas e incidências na documentação técnica do eSocial",
            "Verificar o tpRubr da rubrica e os campos codIncCP, codIncIRRF, codIncFGTS",
            "Alinhar os códigos de incidência com a natureza correta da rubrica",
            "Se a rubrica tem natureza errada: excluir via S-3000 e recriar com a natureza correta",
            "Retransmitir o S-1010 com incidências compatíveis"
        ],
        "validacao": "Confirmar que a rubrica consta na tabela do eSocial com natureza e incidências coerentes. S-1010 com cdResposta=201.",
        "tempo_estimado": "2h",
        "impacto": "médio",
        "tags": ["S-1010", "E602", "rubrica", "natureza", "incidência", "FGTS", "IRRF", "tpRubr", "tabela"]
    },
    {
        "id": "KB027",
        "evento": "S-1020",
        "codigo_erro": "E100",
        "titulo": "Lotação tributária S-1020 já cadastrada — usar retificação",
        "descricao": "S-1020 (Tabela de Lotações Tributárias) rejeitado com E100. O código de lotação tributária já existe na tabela do empregador no eSocial e não pode ser inserido novamente como evento original.",
        "causa_raiz": "A lotação tributária foi cadastrada previamente com sucesso. Qualquer alteração em lotação existente deve ser feita com S-1020 em modo retificação (indRetif=2), referenciando o nrRec do evento original. O código de lotação é chave única por empregador.",
        "passos_resolucao": [
            "Localizar o S-1020 original na plataforma eSocial e copiar o nrRec",
            "No XML, definir indRetif=2 e preencher nrRecEvt com o nrRec do S-1020 original",
            "Atualizar os campos necessários (FPAS, código de terceiros, etc.)",
            "Retransmitir o S-1020 como retificação",
            "Confirmar aceite na plataforma"
        ],
        "validacao": "Consultar a lotação tributária na tabela do empregador e confirmar dados atualizados. S-1020 com cdResposta=201.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1020", "E100", "lotação tributária", "FPAS", "indRetif", "retificação", "tabela"]
    },
    {
        "id": "KB028",
        "evento": "S-1020",
        "codigo_erro": "E144",
        "titulo": "CNO de obra inativo ou cancelado na lotação tributária",
        "descricao": "S-1020 rejeitado com E144. O Cadastro Nacional de Obras (CNO) informado na lotação tributária está inativo, cancelado, ou não existe na base da RFB.",
        "causa_raiz": "Quando a lotação tributária se refere a uma obra de construção civil (tpLotacao=01 ou 02), o CNO informado é validado contra a base da RFB. CNOs encerrados após conclusão da obra, CNOs com erro de digitação, ou CNOs de outra empresa geram E144.",
        "passos_resolucao": [
            "Consultar a situação do CNO no portal da RFB: https://www.gov.br/receitafederal/pt-br",
            "Verificar se o CNO informado corresponde à obra correta e ao empregador correto",
            "Se CNO encerrado indevidamente: solicitar reativação junto à RFB",
            "Se CNO errado: corrigir o número do CNO no XML do S-1020",
            "Retransmitir o S-1020 com o CNO ativo e correto"
        ],
        "validacao": "Confirmar situação ativa do CNO na RFB antes de retransmitir. S-1020 deve ser aceito com cdResposta=201.",
        "tempo_estimado": "2-4h",
        "impacto": "médio",
        "tags": ["S-1020", "E144", "CNO", "obra", "construção civil", "RFB", "lotação tributária", "tabela"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO C — S-3000: EXCLUSÃO DE EVENTOS (GAPS)
    # ──────────────────────────────────────────────────────
    {
        "id": "KB029",
        "evento": "S-3000",
        "codigo_erro": "E311",
        "titulo": "Evento a excluir não existe ou nunca foi processado no eSocial",
        "descricao": "S-3000 (Exclusão de Eventos) rejeitado com E311. O nrRec informado para exclusão não corresponde a nenhum evento processado com sucesso na plataforma para o empregador.",
        "causa_raiz": "O nrRec referenciado no S-3000 pode: pertencer a um evento que nunca teve aceite (cdResposta diferente de 201), pertencer a outro CNPJ empregador, ter sido gerado por erro de digitação, ou o evento pode já ter sido excluído anteriormente. O E311 indica ausência do evento na base ativa do eSocial.",
        "passos_resolucao": [
            "Consultar o histórico de eventos na plataforma eSocial e verificar o status do nrRec informado",
            "Confirmar que o nrRec pertence ao mesmo CNPJ empregador transmissor",
            "Verificar se o evento original foi processado com cdResposta=201 (aceite)",
            "Se o evento nunca foi aceito: nenhuma exclusão é necessária pois não há registro ativo",
            "Se o nrRec está incorreto: localizar o nrRec correto na plataforma e corrigir no S-3000",
            "Retransmitir o S-3000 somente com nrRec de evento efetivamente processado"
        ],
        "validacao": "Verificar na plataforma eSocial que o evento referenciado existia como ativo antes do S-3000. Após exclusão, status deve mudar para 'Excluído'.",
        "tempo_estimado": "1-2h",
        "impacto": "médio",
        "tags": ["S-3000", "E311", "exclusão", "nrRec", "evento inexistente", "cancelamento"]
    },
    {
        "id": "KB030",
        "evento": "S-3000",
        "codigo_erro": "E428",
        "titulo": "Exclusão de S-1200 bloqueada — S-1210 dependente ainda ativo",
        "descricao": "S-3000 para exclusão de S-1200 rejeitado com E428. Existe um S-1210 (Pagamentos de Rendimentos do Trabalho) processado que referencia o S-1200 que se deseja excluir, impedindo a exclusão direta.",
        "causa_raiz": "O eSocial mantém integridade referencial entre eventos. Um S-1210 que referencie o nrRec do S-1200 cria dependência. A exclusão do S-1200 sem antes excluir o S-1210 dependente viola essa integridade e resulta em E428. A regra de negócio exige exclusão na ordem inversa de criação.",
        "passos_resolucao": [
            "Identificar todos os S-1210 que referenciam o nrRec do S-1200 a ser excluído",
            "Enviar S-3000 para excluir primeiro cada S-1210 dependente",
            "Aguardar confirmação de exclusão de todos os S-1210",
            "Enviar S-3000 para excluir o S-1200 agora sem dependentes",
            "Verificar na plataforma que o S-1200 está com status 'Excluído'"
        ],
        "validacao": "Confirmar na plataforma que S-1210 e S-1200 estão com status 'Excluído'. Nenhum evento ativo deve referenciar o nrRec excluído.",
        "tempo_estimado": "2-3h",
        "impacto": "alto",
        "tags": ["S-3000", "E428", "exclusão", "S-1200", "S-1210", "dependência", "integridade referencial"]
    },
    {
        "id": "KB031",
        "evento": "S-3000",
        "codigo_erro": "E440",
        "titulo": "Exclusão de admissão S-2200 bloqueada por eventos dependentes",
        "descricao": "S-3000 para exclusão de S-2200 (admissão) rejeitado com E440. Existem eventos posteriores que dependem do vínculo criado pelo S-2200, como S-2206 (alteração contratual), S-2230 (afastamento) ou S-2299 (desligamento) ainda ativos.",
        "causa_raiz": "O eSocial não permite excluir um evento que serve de base para outros eventos do mesmo trabalhador. O S-2200 cria o vínculo empregatício do qual dependem todos os eventos subsequentes do trabalhador. Para excluir a admissão, todos os eventos posteriores devem ser excluídos primeiro na ordem inversa de criação.",
        "passos_resolucao": [
            "Levantar todos os eventos do trabalhador posteriores ao S-2200 na plataforma (S-2206, S-2230, S-2299, S-1200, etc.)",
            "Excluir via S-3000 os eventos na ordem inversa: primeiro S-2299 ou eventos mais recentes, depois S-2230, S-2206",
            "Aguardar confirmação de exclusão de cada evento",
            "Excluir por último o S-2200 (admissão) após remoção de todos os dependentes",
            "Verificar que não restam eventos ativos para o trabalhador nesse empregador"
        ],
        "validacao": "Confirmar na plataforma que todos os eventos do vínculo estão com status 'Excluído' e que não há pendências para o CPF do trabalhador.",
        "tempo_estimado": "3-5h",
        "impacto": "alto",
        "tags": ["S-3000", "E440", "exclusão", "S-2200", "admissão", "vínculo", "dependência", "desligamento"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO D — S-2200 / S-2190 / S-2300: ADMISSÃO E TSVE
    # ──────────────────────────────────────────────────────
    {
        "id": "KB032",
        "evento": "S-2200",
        "codigo_erro": "E312",
        "titulo": "Admissão duplicada — CPF já possui vínculo ativo no empregador",
        "descricao": "S-2200 (Admissão de Trabalhador) rejeitado com E312. O CPF do trabalhador já possui vínculo empregatício ativo no mesmo empregador no eSocial, impedindo nova admissão sem antes encerrar o vínculo anterior.",
        "causa_raiz": "O eSocial não permite dois vínculos simultâneos do mesmo CPF com o mesmo empregador (mesmo CNPJ raiz). Isso ocorre quando: o trabalhador foi desligado mas o S-2299 não foi enviado, houve retorno de afastamento não registrado, ou o S-2200 foi enviado em duplicata por erro de sistema.",
        "passos_resolucao": [
            "Consultar os vínculos ativos do CPF na plataforma eSocial para o empregador",
            "Verificar se há vínculo anterior não encerrado e seu nrRec de S-2200",
            "Se o trabalhador foi desligado sem S-2299: enviar o S-2299 com a data real de desligamento",
            "Aguardar processamento do S-2299 e confirmação de encerramento do vínculo",
            "Retransmitir o S-2200 de nova admissão após confirmação do encerramento",
            "Verificar se não há outros eventos periódicos pendentes do vínculo anterior"
        ],
        "validacao": "Confirmar que o vínculo anterior está encerrado na plataforma antes de reenviar o S-2200. Nova admissão deve ser aceita com cdResposta=201.",
        "tempo_estimado": "3-4h",
        "impacto": "alto",
        "tags": ["S-2200", "E312", "admissão", "vínculo duplicado", "CPF", "desligamento", "S-2299", "dtAdm", "cpfTrab"]
    },
    {
        "id": "KB033",
        "evento": "S-2200",
        "codigo_erro": "E529",
        "titulo": "Categoria do trabalhador inválida para o tipo de contrato informado",
        "descricao": "S-2200 rejeitado com E529. A categoria do trabalhador (codCateg) informada é incompatível com o tipo de contrato (tpRegTrab), o tipo de jornada, ou outros atributos do vínculo declarados no evento.",
        "causa_raiz": "O eSocial define regras de compatibilidade entre categorias de trabalhadores e tipos de contrato. Exemplos: categoria 101 (empregado geral) não pode ser combinada com tpRegTrab=2 (estatutário); categoria 721 (contribuinte individual) não pode ter jornada de trabalho informada; domésticos têm restrições específicas de categoria.",
        "passos_resolucao": [
            "Consultar a tabela de categorias de trabalhadores na documentação técnica do eSocial",
            "Verificar a combinação codCateg x tpRegTrab x tpJornada usada no XML",
            "Identificar qual campo está incompatível com a regra de negócio do eSocial",
            "Corrigir a categoria ou os atributos do contrato para combinação válida",
            "Retransmitir o S-2200 com os dados corrigidos"
        ],
        "validacao": "Confirmar que a combinação codCateg e tipo de contrato é válida na documentação antes de retransmitir. S-2200 aceito com cdResposta=201.",
        "tempo_estimado": "2h",
        "impacto": "médio",
        "tags": ["S-2200", "E529", "categoria", "codCateg", "contrato", "tpRegTrab", "admissão", "incompatibilidade"]
    },
    {
        "id": "KB034",
        "evento": "S-2200",
        "codigo_erro": "E440",
        "titulo": "Data de admissão anterior ao início da obrigatoriedade do eSocial",
        "descricao": "S-2200 rejeitado com E440. A data de admissão informada é anterior ao período mínimo aceito pelo eSocial para o grupo do empregador, ou é anterior à data de início da obrigatoriedade do evento S-2200.",
        "causa_raiz": "O eSocial só aceita eventos com datas dentro da janela de transmissão permitida para cada grupo de empregadores. Datas de admissão muito antigas (antes do início do eSocial para o grupo) ou fora da janela de retroatividade permitida geram E440. Também ocorre quando o campo dtAdm contém data futura por erro de digitação.",
        "passos_resolucao": [
            "Verificar o calendário de obrigatoriedade do eSocial para o grupo do empregador",
            "Confirmar a data de admissão real do trabalhador nos documentos físicos (CTPS, contrato)",
            "Se data anterior à obrigatoriedade: verificar as regras de envio de eventos históricos com a RFB",
            "Se data futura por erro de digitação: corrigir o campo dtAdm",
            "Contactar o e-CAC para orientação sobre admissões retroativas fora da janela permitida",
            "Retransmitir após correção"
        ],
        "validacao": "Confirmar que a data de admissão está dentro da janela permitida e que o S-2200 é aceito com cdResposta=201.",
        "tempo_estimado": "2-4h",
        "impacto": "médio",
        "tags": ["S-2200", "E440", "admissão", "dtAdm", "data retroativa", "obrigatoriedade", "janela transmissão"]
    },
    {
        "id": "KB035",
        "evento": "S-2190",
        "codigo_erro": "E460",
        "titulo": "CPF do trabalhador sem vínculo (TSVE) inválido ou não cadastrado na RFB",
        "descricao": "S-2190 (Registro Preliminar de Trabalhador) rejeitado com E460. O CPF informado para o trabalhador sem vínculo empregatício não consta na base da Receita Federal ou está em situação irregular.",
        "causa_raiz": "O S-2190 é o evento de registro preliminar para trabalhadores sem vínculo. O eSocial valida o CPF contra a RFB em tempo real. CPF com erro de digitação, CPF de trabalhador estrangeiro não cadastrado na RFB, ou CPF em situação irregular (cancelado, pendente de regularização) resultam em E460.",
        "passos_resolucao": [
            "Consultar a situação do CPF na RFB: https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp",
            "Se CPF com erro de digitação: corrigir e retransmitir o S-2190",
            "Se CPF irregular: o trabalhador deve regularizar junto à RFB antes do registro",
            "Para trabalhador estrangeiro: verificar o processo de obtenção de CPF via RFB ou consulado",
            "Após confirmação de CPF regular: retransmitir o S-2190"
        ],
        "validacao": "Confirmar situação 'Regular' do CPF na RFB antes de retransmitir. S-2190 aceito com cdResposta=201.",
        "tempo_estimado": "Variável — depende da regularização do trabalhador",
        "impacto": "alto",
        "tags": ["S-2190", "E460", "CPF", "RFB", "trabalhador sem vínculo", "TSVE", "registro preliminar"]
    },
    {
        "id": "KB036",
        "evento": "S-2190",
        "codigo_erro": "E312",
        "titulo": "Trabalhador S-2190 já possui vínculo ativo — conflito com S-2200 existente",
        "descricao": "S-2190 (Registro Preliminar) rejeitado com E312. O CPF do trabalhador já possui um vínculo empregatício formal ativo (S-2200) no mesmo empregador, tornando o registro preliminar inválido.",
        "causa_raiz": "O S-2190 é um evento temporário para registro antes da admissão formal. Se o trabalhador já possui um vínculo formal via S-2200 ativo, enviar S-2190 cria conflito pois um trabalhador não pode ser simultaneamente contratado e em registro preliminar no mesmo empregador. O E312 indica a existência de vínculo ativo incompatível com o registro preliminar.",
        "passos_resolucao": [
            "Consultar a situação do CPF na plataforma eSocial para o empregador",
            "Identificar se existe S-2200 ativo para o trabalhador",
            "Se o S-2200 é legítimo: o S-2190 não é necessário — o trabalhador já está admitido formalmente",
            "Se o S-2200 foi enviado por engano: enviar S-2299 para encerrar o vínculo indevido antes de enviar S-2190",
            "Alinhar com o departamento de RH o fluxo correto de admissão do trabalhador"
        ],
        "validacao": "Confirmar que há apenas um evento ativo para o CPF (ou S-2190 ou S-2200, não ambos) na plataforma eSocial.",
        "tempo_estimado": "2-3h",
        "impacto": "alto",
        "tags": ["S-2190", "E312", "registro preliminar", "S-2200", "vínculo ativo", "conflito", "TSVE"]
    },
    {
        "id": "KB037",
        "evento": "S-2300",
        "codigo_erro": "E529",
        "titulo": "Categoria inválida para trabalhador sem vínculo empregatício",
        "descricao": "S-2300 (Trabalhador Sem Vínculo de Emprego — Início) rejeitado com E529. A categoria informada (codCateg) não é compatível com o tipo de trabalhador sem vínculo ou com os demais atributos do evento.",
        "causa_raiz": "O S-2300 é restrito a determinadas categorias de trabalhadores sem vínculo empregatício formal (contribuintes individuais, cooperados, estagiários, etc.). Categorias de empregados CLT, categorias exclusivas de servidores públicos, ou combinações inválidas de categoria com tipo de atividade geram E529. O eSocial valida a tabela de categorias permitidas para S-2300.",
        "passos_resolucao": [
            "Consultar as categorias permitidas para S-2300 na documentação técnica do eSocial",
            "Verificar se o trabalhador se enquadra como TSVE (Trabalhador Sem Vínculo de Emprego)",
            "Se for empregado CLT: usar S-2200 (admissão) ao invés de S-2300",
            "Se for TSVE: identificar a categoria correta (ex: 721 - contribuinte individual, 731 - cooperado)",
            "Corrigir o codCateg no XML e retransmitir o S-2300"
        ],
        "validacao": "Confirmar que a categoria informada consta na lista de categorias válidas para S-2300. S-2300 aceito com cdResposta=201.",
        "tempo_estimado": "2h",
        "impacto": "médio",
        "tags": ["S-2300", "E529", "categoria", "TSVE", "trabalhador sem vínculo", "contribuinte individual", "codCateg"]
    },
    {
        "id": "KB038",
        "evento": "S-2300",
        "codigo_erro": "E460",
        "titulo": "CPF do trabalhador autônomo não consta na base da RFB",
        "descricao": "S-2300 rejeitado com E460. O CPF do trabalhador sem vínculo empregatício (autônomo, contribuinte individual, cooperado) não está cadastrado na RFB ou encontra-se em situação irregular.",
        "causa_raiz": "Assim como no S-2200, o S-2300 exige validação do CPF em tempo real contra a base da RFB. Trabalhadores autônomos com CPF pendente de regularização, estrangeiros sem CPF brasileiro, ou CPF digitado incorretamente geram E460. A regra de validação é idêntica para todos os eventos que declaram CPF de trabalhador.",
        "passos_resolucao": [
            "Consultar a situação do CPF na RFB",
            "Se CPF com erro de digitação: corrigir e retransmitir",
            "Se CPF irregular: orientar o trabalhador a regularizar o CPF junto à RFB",
            "Para autônomos estrangeiros: verificar a necessidade e processo de obtenção de CPF no Brasil",
            "Retransmitir o S-2300 somente após confirmação de CPF em situação 'Regular'"
        ],
        "validacao": "CPF com situação 'Regular' na RFB. S-2300 processado com cdResposta=201.",
        "tempo_estimado": "Variável",
        "impacto": "alto",
        "tags": ["S-2300", "E460", "CPF", "RFB", "autônomo", "TSVE", "contribuinte individual", "irregular"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO E — S-2400: BENEFICIÁRIOS INSS
    # ──────────────────────────────────────────────────────
    {
        "id": "KB039",
        "evento": "S-2400",
        "codigo_erro": "E460",
        "titulo": "CPF do beneficiário INSS inválido ou não cadastrado na RFB",
        "descricao": "S-2400 (Cadastro de Beneficiário — Início do Benefício) rejeitado com E460. O CPF do beneficiário não está cadastrado na Receita Federal ou está em situação irregular, impedindo o registro do benefício previdenciário.",
        "causa_raiz": "O S-2400 declara o início do gozo de benefício previdenciário (aposentadoria, pensão, auxílio-doença, etc.) para o INSS. O eSocial valida o CPF do beneficiário na base da RFB. CPFs irregulares, de beneficiários falecidos não baixados, ou com erro de digitação geram E460.",
        "passos_resolucao": [
            "Consultar a situação do CPF do beneficiário na RFB",
            "Se CPF com erro de digitação: corrigir e retransmitir o S-2400",
            "Se CPF de beneficiário falecido: verificar se o benefício deve ser transferido para dependente via espécie correta",
            "Se CPF irregular: providenciar regularização junto à RFB com a documentação do beneficiário",
            "Retransmitir o S-2400 após confirmação de CPF regular"
        ],
        "validacao": "CPF do beneficiário com situação 'Regular' na RFB. S-2400 processado com cdResposta=201.",
        "tempo_estimado": "Variável — depende da regularização do beneficiário",
        "impacto": "alto",
        "tags": ["S-2400", "E460", "CPF", "beneficiário", "INSS", "previdência", "RFB", "benefício"]
    },
    {
        "id": "KB040",
        "evento": "S-2400",
        "codigo_erro": "E529",
        "titulo": "Espécie de benefício incompatível com a categoria do beneficiário",
        "descricao": "S-2400 rejeitado com E529. A espécie de benefício INSS informada (codBenef ou tpBenef) é incompatível com a categoria do beneficiário, o tipo de incapacidade declarada, ou outros atributos do evento.",
        "causa_raiz": "O eSocial define regras de compatibilidade entre espécies de benefícios e categorias de beneficiários. Por exemplo: benefício de aposentadoria por invalidez exige laudo médico pericial; pensão por morte requer CPF de dependente; auxílio-doença tem prazo mínimo de afastamento. Incompatibilidades entre esses elementos geram E529.",
        "passos_resolucao": [
            "Consultar a tabela de espécies de benefícios e categorias compatíveis na documentação do eSocial",
            "Verificar qual espécie de benefício (tpBenef/codBenef) é adequada para a situação do beneficiário",
            "Confirmar que todos os atributos obrigatórios para a espécie estão preenchidos (ex.: dtInicioDoc para benefícios com laudo)",
            "Corrigir o código do benefício ou os atributos do evento",
            "Retransmitir o S-2400 com dados compatíveis"
        ],
        "validacao": "Confirmar que a combinação espécie e categoria é válida na documentação. S-2400 aceito com cdResposta=201.",
        "tempo_estimado": "2-3h",
        "impacto": "médio",
        "tags": ["S-2400", "E529", "benefício", "INSS", "espécie", "categoria", "codBenef", "incompatibilidade"]
    },
    {
        "id": "KB041",
        "evento": "S-2400",
        "codigo_erro": "E312",
        "titulo": "Beneficiário já possui cadastro ativo para o mesmo benefício no empregador",
        "descricao": "S-2400 rejeitado com E312. O CPF do beneficiário já possui um registro ativo de benefício do mesmo tipo no mesmo empregador no eSocial, impedindo um novo cadastro sem encerramento do anterior.",
        "causa_raiz": "Cada beneficiário pode ter apenas um registro ativo por tipo de benefício por empregador no eSocial. Enviar S-2400 para um beneficiário que já tem benefício ativo (sem encerramento via S-2400 com dtFimBenef ou evento de suspensão) gera E312. Também ocorre com envio em duplicata por erro de sistema.",
        "passos_resolucao": [
            "Consultar os benefícios ativos do CPF na plataforma eSocial para o empregador",
            "Verificar se há um S-2400 ativo para o mesmo tipo de benefício",
            "Se for uma renovação: encerrar o benefício anterior via S-2400 com dtFimBenef antes de iniciar novo",
            "Se for duplicata: identificar o S-2400 original e não reenviar",
            "Retransmitir somente após encerramento do benefício anterior"
        ],
        "validacao": "Confirmar que não há benefício ativo duplicado para o CPF. Novo S-2400 aceito com cdResposta=201.",
        "tempo_estimado": "2h",
        "impacto": "médio",
        "tags": ["S-2400", "E312", "benefício", "duplicata", "INSS", "beneficiário", "encerramento", "dtFimBenef"]
    },
    {
        "id": "KB042",
        "evento": "S-2400",
        "codigo_erro": "E601",
        "titulo": "Data de início do benefício anterior à competência mínima aceita",
        "descricao": "S-2400 rejeitado com E601. A data de início do benefício (dtIniBenef) informada é anterior à data mínima aceita pelo eSocial para o tipo de benefício ou está fora da janela de transmissão permitida.",
        "causa_raiz": "O eSocial define datas mínimas de vigência para cada tipo de benefício previdenciário conforme o calendário de implantação. Benefícios com datas muito antigas, anteriores ao início da obrigatoriedade do eSocial para o empregador, ou com datas futuras por erro de preenchimento geram E601.",
        "passos_resolucao": [
            "Verificar a data real de início do benefício nos documentos do INSS ou decisão judicial",
            "Consultar a janela de transmissão permitida para o tipo de benefício na documentação do eSocial",
            "Corrigir o campo dtIniBenef com a data correta e dentro da janela permitida",
            "Se a data for anterior à janela: verificar com a RFB a possibilidade de transmissão retroativa",
            "Retransmitir o S-2400 com a data corrigida"
        ],
        "validacao": "Confirmar que dtIniBenef está dentro da janela permitida. S-2400 aceito com cdResposta=201.",
        "tempo_estimado": "2h",
        "impacto": "médio",
        "tags": ["S-2400", "E601", "benefício", "dtIniBenef", "data", "competência", "INSS", "prazo"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO F — S-1200 / S-1299: REMUNERAÇÃO E FECHAMENTO (GAPS)
    # ──────────────────────────────────────────────────────
    {
        "id": "KB043",
        "evento": "S-1200",
        "codigo_erro": "E301",
        "titulo": "Base de cálculo FGTS no S-1200 diverge do saldo esperado",
        "descricao": "S-1200 rejeitado com E301. Os valores de base de cálculo FGTS informados no evento de remuneração estão inconsistentes com o saldo acumulado do trabalhador ou com as rubricas que compõem a base FGTS declaradas no S-1010.",
        "causa_raiz": "O eSocial valida que a soma das rubricas com incidência FGTS (codIncFGTS=11) corresponde à base de FGTS declarada. Divergências ocorrem quando: rubricas de FGTS estão com código de incidência errado no S-1010, a folha foi recalculada após o envio do S-1200 original, ou há diferença de arredondamento entre sistemas.",
        "passos_resolucao": [
            "Conferir as rubricas com incidência FGTS no S-1010 (codIncFGTS=11) e somar os valores do período",
            "Comparar a soma com o campo vrBcFGTS do S-1200",
            "Identificar rubricas com incidência incorreta no S-1010 e corrigir via retificação",
            "Recalcular a folha após as correções do S-1010",
            "Retransmitir o S-1200 com os valores de base FGTS corretos",
            "Verificar o extrato FGTS do trabalhador após processamento"
        ],
        "validacao": "Confirmar que a soma das rubricas FGTS bate com vrBcFGTS no S-1200 aceito. Verificar saldo FGTS no extrato do trabalhador.",
        "tempo_estimado": "3-4h",
        "impacto": "alto",
        "tags": ["S-1200", "E301", "FGTS", "base de cálculo", "vrBcFGTS", "codIncFGTS", "rubrica", "incidência", "remuneração"]
    },
    {
        "id": "KB044",
        "evento": "S-1200",
        "codigo_erro": "E450",
        "titulo": "Rubricas do S-1200 sem correspondência na tabela S-1010",
        "descricao": "S-1200 rejeitado com E450. O evento de remuneração utiliza códigos de rubricas que não estão cadastrados na tabela de rubricas (S-1010) do empregador no eSocial.",
        "causa_raiz": "O eSocial exige que cada rubrica usada no S-1200 esteja previamente cadastrada via S-1010. Se a tabela de rubricas não foi completamente carregada, se houve exclusão inadvertida de rubrica via S-3000, ou se o sistema de folha usa códigos de rubrica diferentes dos cadastrados no eSocial, o S-1200 é rejeitado.",
        "passos_resolucao": [
            "Identificar os códigos de rubrica do S-1200 que estão retornando E450",
            "Consultar a tabela de rubricas cadastradas no eSocial (S-1010) para o empregador",
            "Para rubricas não cadastradas: enviar S-1010 com a(s) rubrica(s) faltante(s)",
            "Aguardar processamento do(s) S-1010",
            "Retransmitir o S-1200 após confirmação das rubricas cadastradas"
        ],
        "validacao": "Verificar que todas as rubricas do S-1200 constam na tabela S-1010 do empregador. S-1200 aceito com cdResposta=201.",
        "tempo_estimado": "2-3h",
        "impacto": "médio",
        "tags": ["S-1200", "E450", "rubrica", "S-1010", "tabela", "remuneração", "código rubrica", "folha", "codRubr", "nrRubr"]
    },
    {
        "id": "KB045",
        "evento": "S-1299",
        "codigo_erro": "E312",
        "titulo": "Fechamento S-1299 rejeitado — vínculos sem S-1200 na competência",
        "descricao": "S-1299 (Fechamento dos Eventos Periódicos) rejeitado com E312. O eSocial identificou trabalhadores com vínculo ativo para a competência que não possuem evento S-1200 (Remuneração) processado, impedindo o fechamento.",
        "causa_raiz": "O S-1299 sinaliza que todos os eventos periódicos da competência foram transmitidos. Se algum trabalhador ativo não tem S-1200 correspondente, ou se há S-1200 com erro/rejeição pendente para a competência, o eSocial bloqueia o fechamento com E312 pois a obrigação periódica não foi cumprida para todos os vínculos.",
        "passos_resolucao": [
            "Gerar relatório na plataforma eSocial de trabalhadores com vínculo ativo sem S-1200 para a competência",
            "Identificar se os S-1200 faltantes são devidos (trabalhadores em afastamento sem remuneração podem ter situação diferente)",
            "Enviar os S-1200 faltantes para todos os trabalhadores que geraram remuneração na competência",
            "Verificar e corrigir S-1200 com erros pendentes",
            "Retransmitir o S-1299 somente após todos os S-1200 processados"
        ],
        "validacao": "Confirmar na plataforma que não há vínculos sem S-1200 para a competência. S-1299 aceito com cdResposta=201.",
        "tempo_estimado": "4-6h",
        "impacto": "alto",
        "tags": ["S-1299", "E312", "fechamento", "S-1200", "vínculo", "competência", "remuneração", "pendência"]
    },
    {
        "id": "KB046",
        "evento": "S-1299",
        "codigo_erro": "E430",
        "titulo": "Fechamento S-1299 já processado para a competência — usar retificação",
        "descricao": "S-1299 rejeitado com E430. O fechamento da competência já foi processado anteriormente com sucesso. Um novo S-1299 para a mesma competência deve ser enviado como retificação.",
        "causa_raiz": "O S-1299 é o evento de fechamento da competência e só pode existir uma versão ativa por competência. Reenviar o S-1299 com indRetif=1 para uma competência já fechada gera E430. Para reabrir a competência (ex.: para incluir S-1200 esquecido), deve-se usar o S-1299 em modo retificação ou seguir o fluxo de reabertura.",
        "passos_resolucao": [
            "Consultar na plataforma eSocial o S-1299 já processado e copiar o nrRec",
            "Verificar se a necessidade é de retificação do fechamento ou de inclusão de eventos periódicos",
            "Se for retificação: definir indRetif=2 e preencher nrRecEvt com o nrRec do S-1299 original",
            "Se precisar incluir S-1200 após fechamento: verificar se a competência está reaberta ou abrir chamado na RFB",
            "Retransmitir o S-1299 como retificação"
        ],
        "validacao": "Confirmar na plataforma que o S-1299 retificado está com status processado e competência encerrada corretamente.",
        "tempo_estimado": "1-2h",
        "impacto": "médio",
        "tags": ["S-1299", "E430", "fechamento", "competência", "duplicata", "indRetif", "retificação", "reabertura"]
    },
    {
        "id": "KB047",
        "evento": "S-1299",
        "codigo_erro": "E320",
        "titulo": "Competência do fechamento S-1299 encerrada — prazo expirado",
        "descricao": "S-1299 rejeitado com E320. O período de apuração (perApur) informado no fechamento corresponde a uma competência cujo prazo de transmissão já encerrou no eSocial.",
        "causa_raiz": "Assim como o S-1200, o fechamento S-1299 tem prazo definido. Se a competência está fora da janela de transmissão permitida, o eSocial rejeita com E320. Isso ocorre quando há atraso significativo no envio da folha ou quando se tenta fechar competências muito antigas sem o processo de regularização adequado.",
        "passos_resolucao": [
            "Verificar o calendário de obrigações do eSocial para identificar o prazo da competência",
            "Contatar o e-CAC da RFB para orientação sobre fechamentos fora do prazo",
            "Verificar se há programa de regularização aplicável (PERT ou similar)",
            "Documentar o atraso e solicitar orientação formal da RFB",
            "Implementar alertas de calendário para evitar recorrência"
        ],
        "validacao": "Confirmar com a RFB a possibilidade de transmissão extemporânea antes de tentar reenvio.",
        "tempo_estimado": "Variável — pode exigir contato com RFB",
        "impacto": "crítico",
        "tags": ["S-1299", "E320", "fechamento", "competência", "prazo", "extemporâneo", "perApur", "RFB"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO G — ERROS GENÉRICOS DE ALTA FREQUÊNCIA
    # ──────────────────────────────────────────────────────
    {
        "id": "KB048",
        "evento": "Qualquer",
        "codigo_erro": "E001",
        "titulo": "XML sem assinatura digital válida — rejeição por falta de assinatura",
        "descricao": "Evento rejeitado com E001. O XML transmitido não possui assinatura digital ou a assinatura presente é inválida, malformada, ou não foi aplicada ao elemento correto do documento.",
        "causa_raiz": "O eSocial exige que todos os XMLs sejam assinados digitalmente com certificado ICP-Brasil antes da transmissão. E001 ocorre quando: o middleware não aplicou a assinatura, a assinatura foi aplicada em elemento incorreto do XML, o certificado usado para assinar não é o mesmo que o da transmissão, ou a assinatura foi corrompida durante a serialização do XML.",
        "passos_resolucao": [
            "Verificar nos logs do middleware se o processo de assinatura foi executado sem erros",
            "Confirmar que a assinatura está sendo aplicada no elemento correto: tag <Signature> dentro do elemento raiz do evento",
            "Verificar que o certificado A1 ou A3 está corretamente configurado no middleware",
            "Testar a assinatura com ferramenta offline de validação de XML assinado (ex.: SignatureValidator)",
            "Regenerar e retransmitir o XML com assinatura correta",
            "Se o problema persistir: consultar o fornecedor do middleware"
        ],
        "validacao": "Validar a assinatura digital do XML com ferramenta de verificação antes de transmitir. Confirmar aceite sem E001.",
        "tempo_estimado": "2-4h",
        "impacto": "crítico",
        "tags": ["E001", "assinatura digital", "XML", "certificado", "ICP-Brasil", "middleware", "signature", "rejeição"]
    },
    {
        "id": "KB049",
        "evento": "Qualquer",
        "codigo_erro": "MA105",
        "titulo": "Campo indRetif com valor inválido — fora do domínio permitido",
        "descricao": "Evento rejeitado com MA105. O campo indRetif contém valor fora do domínio permitido pelo eSocial. Os únicos valores válidos são 1 (evento original) e 2 (retificação), sendo que o valor 3 é aceito apenas em contextos específicos de anulação.",
        "causa_raiz": "O indRetif é um campo de domínio restrito. Valores como 0, 3 (fora do contexto correto), strings, ou campos em branco geram MA105. Também ocorre quando o sistema de folha envia indRetif=3 sem o contexto adequado, ou quando há conversão de tipo de dados que corrompe o valor numérico.",
        "passos_resolucao": [
            "Verificar o valor atual de indRetif no XML rejeitado",
            "Para eventos novos (primeira transmissão): definir indRetif=1",
            "Para correção de evento já enviado: definir indRetif=2 e preencher nrRecEvt",
            "Verificar o sistema de geração XML para garantir que o campo está sendo gerado corretamente",
            "Retransmitir com indRetif no valor correto"
        ],
        "validacao": "Confirmar que indRetif=1 para eventos novos ou indRetif=2 com nrRecEvt para retificações. Evento aceito com cdResposta=201.",
        "tempo_estimado": "1h",
        "impacto": "alto",
        "tags": ["MA105", "indRetif", "domínio", "campo inválido", "retificação", "original", "validação schema"]
    },
    {
        "id": "KB050",
        "evento": "Qualquer",
        "codigo_erro": "E999",
        "titulo": "Erro interno do webservice — retentativa recomendada",
        "descricao": "Transmissão retornou E999 (erro interno do servidor do eSocial). Este código indica falha no lado do governo, não no XML transmitido. O evento pode estar correto e deve ser retransmitido após aguardar estabilização do ambiente.",
        "causa_raiz": "E999 é um código genérico de erro interno do webservice do eSocial, equivalente a um HTTP 500. Causas incluem: instabilidade nos servidores do governo, manutenção programada sem aviso prévio, sobrecarga em datas críticas de folha, ou falhas transitórias na integração entre sistemas internos da RFB.",
        "passos_resolucao": [
            "Verificar o status operacional do ambiente eSocial: https://servicos.receita.fazenda.gov.br",
            "Aguardar 15-30 minutos e tentar retransmitir",
            "Se persistir: implementar retry com backoff exponencial (15min, 30min, 1h)",
            "Monitorar canais oficiais da RFB e eSocial para informes de instabilidade",
            "Registrar o incidente com data/hora e nrLote para fins de auditoria",
            "Se o erro persistir por mais de 4h: abrir chamado no e-CAC"
        ],
        "validacao": "Retransmitir após estabilização do ambiente e confirmar aceite. Nenhuma correção no XML é necessária para E999.",
        "tempo_estimado": "1-4h (aguardar recuperação do ambiente)",
        "impacto": "médio",
        "tags": ["E999", "erro interno", "webservice", "indisponibilidade", "retry", "servidor", "instabilidade"]
    },
    {
        "id": "KB051",
        "evento": "Qualquer",
        "codigo_erro": "E431",
        "titulo": "Evento duplicado — nrRec já processado no eSocial",
        "descricao": "Evento rejeitado com E431. O número de recibo (nrRec) ou identificação do evento já foi processado anteriormente pelo eSocial, caracterizando transmissão duplicada.",
        "causa_raiz": "E431 ocorre quando o mesmo evento é transmitido mais de uma vez com o mesmo identificador. Causas: sistema de retry enviou o evento múltiplas vezes após timeout, operador retransmitiu manualmente sem verificar status anterior, ou o sistema de integração não verificou o retorno da transmissão anterior antes de reenviar.",
        "passos_resolucao": [
            "Consultar o status do evento na plataforma eSocial usando o nrRec ou identificação do evento",
            "Se o evento já foi aceito (cdResposta=201): nenhuma ação adicional é necessária",
            "Se o evento está com erro: corrigir e retransmitir como retificação (indRetif=2) ou novo evento",
            "Revisar o sistema de retry para evitar reenvio automático de eventos já aceitos",
            "Implementar verificação de status antes de retransmitir"
        ],
        "validacao": "Confirmar na plataforma que o evento original está processado. Para eventos aceitos, nenhuma retransmissão é necessária.",
        "tempo_estimado": "1h",
        "impacto": "médio",
        "tags": ["E431", "duplicata", "nrRec", "reenvio", "retry", "evento duplicado", "transmissão"]
    },
    {
        "id": "KB052",
        "evento": "Qualquer",
        "codigo_erro": "E530",
        "titulo": "Campo obrigatório ausente — validação de schema XSD incompleta",
        "descricao": "Evento rejeitado com E530. Um ou mais campos obrigatórios pelo schema XSD do evento estão ausentes no XML transmitido. O eSocial realiza validação completa de schema antes de processar o evento.",
        "causa_raiz": "O XML não inclui todos os elementos obrigatórios definidos no schema XSD do evento. Isso ocorre quando: o software de geração XML não foi atualizado após mudança de leiaute que tornou novo campo obrigatório, há bugs na serialização XML que omitem tags em determinadas condições, ou campos condicionalmente obrigatórios (obrigatórios dado valor de outro campo) não foram incluídos.",
        "passos_resolucao": [
            "Validar o XML rejeitado contra o schema XSD atual do evento usando ferramenta de validação",
            "Identificar todos os campos apontados como ausentes ou inválidos",
            "Verificar na documentação técnica do eSocial se houve atualização de leiaute que tornou novos campos obrigatórios",
            "Corrigir o software de geração XML para incluir os campos obrigatórios ausentes",
            "Revalidar o XML contra o XSD e retransmitir"
        ],
        "validacao": "Validar o XML contra XSD sem erros antes de transmitir. Evento aceito com cdResposta=201.",
        "tempo_estimado": "2-4h",
        "impacto": "alto",
        "tags": ["E530", "campo obrigatório", "schema", "XSD", "validação", "XML", "leiaute", "ausente"]
    },
    {
        "id": "KB053",
        "evento": "S-1070",
        "codigo_erro": "E602",
        "titulo": "Tipo de processo judicial incompatível com a decisão informada",
        "descricao": "S-1070 (Tabela de Processos Administrativos/Judiciais) rejeitado com E602. O tipo de processo (tpProc) informado é incompatível com a natureza da decisão (indDecisao), os campos de instância, ou outros atributos do processo declarado.",
        "causa_raiz": "O eSocial valida a coerência entre o tipo de processo (administrativo, judicial, arbitral) e os campos de decisão. Por exemplo: processo judicial exige número CNJ no formato correto; processo administrativo tem campos de instância diferentes; decisão favorável ao empregador requer campos distintos de decisão favorável ao trabalhador. Incompatibilidades entre esses elementos geram E602.",
        "passos_resolucao": [
            "Consultar a documentação técnica do eSocial para a tabela de tipos de processo e campos obrigatórios por tipo",
            "Verificar que o tpProc corresponde à natureza real do processo (1=Administrativo, 2=Judicial, 3=Arbitral)",
            "Para processos judiciais: confirmar que o número está no formato CNJ (NNNNNNN-DD.AAAA.J.TT.OOOO)",
            "Verificar a compatibilidade entre indDecisao e os campos de autoria e instância",
            "Corrigir o XML e retransmitir o S-1070"
        ],
        "validacao": "Confirmar que todos os campos do S-1070 são coerentes com o tipo e decisão do processo. S-1070 aceito com cdResposta=201.",
        "tempo_estimado": "1-2h",
        "impacto": "médio",
        "tags": ["S-1070", "E602", "processo judicial", "tpProc", "CNJ", "decisão", "administrativo", "indDecisao"]
    },

    # ──────────────────────────────────────────────────────
    # BLOCO H — EXPANSÃO PRIORITÁRIA (KB054–KB060)
    # ──────────────────────────────────────────────────────
    {
        "id": "KB054",
        "evento": "S-2399",
        "codigo_erro": "E312",
        "titulo": "Encerramento de TSVE sem período de atividade ativo no eSocial",
        "descricao": "S-2399 (Trabalhador Sem Vínculo de Emprego — Término) rejeitado com E312. O eSocial não localiza um S-2300 (TSVE — Início) ativo para o CPF e CNPJ informados, tornando o encerramento inválido por ausência de registro de atividade anterior.",
        "causa_raiz": "O S-2399 é o evento de encerramento do período de atividade de trabalhador sem vínculo (autônomo, contribuinte individual, cooperado, estagiário). Para ser aceito, deve existir um S-2300 ativo correspondente ao mesmo CPF e empregador. O erro E312 ocorre quando: o S-2300 nunca foi enviado, foi excluído via S-3000, está em status de rejeição na plataforma, ou o CPF informado no S-2399 diverge do CPF do S-2300 original.",
        "passos_resolucao": [
            "Consultar o CPF do trabalhador na plataforma eSocial para verificar se existe S-2300 ativo para o empregador",
            "Se nenhum S-2300 existir: enviar o S-2300 com a data de início da atividade do trabalhador antes de transmitir o S-2399",
            "Se o S-2300 foi excluído indevidamente via S-3000: reenviar o S-2300 com os dados originais corretos",
            "Verificar que o CPF no S-2399 é idêntico ao CPF usado no S-2300 correspondente",
            "Aguardar o processamento e confirmação do S-2300 (cdResposta=201) antes de retransmitir o S-2399",
            "Retransmitir o S-2399 com a data de término correta após confirmação do S-2300 ativo"
        ],
        "validacao": "Confirmar S-2300 ativo na plataforma eSocial antes de reenviar. Após envio do S-2399, verificar que o período de atividade do trabalhador está encerrado na plataforma com cdResposta=201.",
        "tempo_estimado": "3-5h",
        "impacto": "alto",
        "tags": ["S-2399", "E312", "TSVE", "autônomo", "S-2300", "término", "contribuinte individual", "cpfTrab"]
    },
    {
        "id": "KB055",
        "evento": "S-2399",
        "codigo_erro": "E460",
        "titulo": "CPF do trabalhador autônomo inválido ou irregular no encerramento S-2399",
        "descricao": "S-2399 (Trabalhador Sem Vínculo de Emprego — Término) rejeitado com E460. O CPF do trabalhador sem vínculo informado no evento de encerramento não está cadastrado na Receita Federal ou encontra-se em situação irregular, impedindo o processamento do término de atividade.",
        "causa_raiz": "O eSocial valida o CPF em tempo real contra a base da RFB em todos os eventos que declaram trabalhadores. No S-2399, o CPF informado pode ter sido alterado em relação ao S-2300 original (erro de digitação no encerramento), o trabalhador pode ter regularizado o CPF após o início mas com número diferente, ou o CPF pode estar em situação irregular na RFB por cancelamento ou pendência de regularização.",
        "passos_resolucao": [
            "Consultar a situação do CPF na RFB: https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp",
            "Comparar o CPF informado no S-2399 com o CPF registrado no S-2300 correspondente na plataforma eSocial",
            "Se houver divergência de CPF: corrigir o campo cpfTrab no S-2399 para o CPF exato do S-2300",
            "Se CPF em situação irregular: orientar o trabalhador a regularizar junto à RFB antes do encerramento",
            "Retransmitir o S-2399 somente após confirmar CPF com situação 'Regular' na RFB e idêntico ao S-2300"
        ],
        "validacao": "Confirmar situação 'Regular' do CPF na RFB e que o CPF é idêntico ao do S-2300 ativo. S-2399 aceito com cdResposta=201.",
        "tempo_estimado": "Variável — depende da regularização do trabalhador",
        "impacto": "alto",
        "tags": ["S-2399", "E460", "CPF", "RFB", "autônomo", "TSVE", "contribuinte individual", "cpfTrab", "irregular"]
    },
    {
        "id": "KB056",
        "evento": "S-2410",
        "codigo_erro": "E312",
        "titulo": "Encerramento de benefício INSS sem S-2400 ativo no eSocial",
        "descricao": "S-2410 (Cadastro de Beneficiário — Fim do Benefício) rejeitado com E312. O eSocial não localiza um S-2400 (Cadastro de Beneficiário — Início do Benefício) ativo para o CPF do beneficiário e o empregador informados, tornando o encerramento inválido.",
        "causa_raiz": "O S-2410 encerra o período de gozo de benefício previdenciário declarado via S-2400. O E312 ocorre quando: o S-2400 de início nunca foi transmitido ou foi rejeitado, o S-2400 foi excluído via S-3000, o CPF do beneficiário no S-2410 diverge do CPF no S-2400, ou o tipo de benefício (codBenef) no S-2410 não corresponde ao tipo cadastrado no S-2400 ativo. O eSocial exige correspondência exata entre início e fim de benefício.",
        "passos_resolucao": [
            "Consultar os benefícios ativos do CPF na plataforma eSocial para o empregador",
            "Verificar se existe S-2400 ativo com o mesmo codBenef que se deseja encerrar",
            "Se o S-2400 não existir: enviar o S-2400 com os dados do início do benefício antes de transmitir o S-2410",
            "Confirmar que o CPF do beneficiário no S-2410 é idêntico ao CPF no S-2400 correspondente",
            "Confirmar que o codBenef no S-2410 corresponde exatamente ao codBenef do S-2400 ativo",
            "Retransmitir o S-2410 somente após confirmação do S-2400 ativo e dados consistentes"
        ],
        "validacao": "Verificar na plataforma que o S-2400 está ativo antes do envio. Após o S-2410, confirmar que o benefício aparece como encerrado com cdResposta=201.",
        "tempo_estimado": "3-4h",
        "impacto": "alto",
        "tags": ["S-2410", "E312", "benefício", "INSS", "S-2400", "encerramento", "codBenef", "beneficiário", "dtFimBenef"]
    },
    {
        "id": "KB057",
        "evento": "S-2210",
        "codigo_erro": "E312",
        "titulo": "CAT rejeitada — trabalhador acidentado sem vínculo ativo no eSocial",
        "descricao": "S-2210 (Comunicação de Acidente de Trabalho) rejeitado com E312. O eSocial não localiza vínculo empregatício ativo para o CPF do trabalhador acidentado no empregador informado, tornando a CAT inválida por ausência de registro de admissão correspondente.",
        "causa_raiz": "A CAT só pode ser registrada para trabalhadores com vínculo ativo no eSocial. O E312 no S-2210 ocorre quando: o S-2200 (admissão) do trabalhador nunca foi enviado ou foi rejeitado, o trabalhador foi desligado via S-2299 antes do registro da CAT, o S-2200 foi excluído indevidamente, ou o CPF informado no S-2210 diverge do CPF registrado no S-2200. Este erro é especialmente crítico pois atrasa o registro previdenciário do acidente junto ao INSS.",
        "passos_resolucao": [
            "Consultar o CPF do trabalhador na plataforma eSocial e verificar a situação do vínculo empregatício",
            "Se não existir S-2200 ativo: enviar o S-2200 com a data de admissão real do trabalhador com urgência",
            "Se o S-2200 existir mas estiver rejeitado: corrigir e reenviar o S-2200 antes da CAT",
            "Verificar que o CPF no S-2210 é idêntico ao CPF registrado no S-2200 ativo",
            "Aguardar processamento e confirmação do S-2200 (cdResposta=201) antes de retransmitir o S-2210",
            "Retransmitir o S-2210 imediatamente após confirmação do vínculo — prazo CAT é 1 dia útil após o acidente",
            "Verificar pendências com o INSS caso o prazo de registro da CAT tenha sido ultrapassado"
        ],
        "validacao": "Confirmar vínculo ativo do trabalhador na plataforma antes de reenviar o S-2210. CAT aceita com cdResposta=201 e registro gerado no INSS.",
        "tempo_estimado": "2-4h (urgente — prazo legal de 1 dia útil)",
        "impacto": "crítico",
        "tags": ["S-2210", "E312", "CAT", "acidente trabalho", "vínculo", "S-2200", "INSS", "cpfTrab", "prazo legal"]
    },
    {
        "id": "KB058",
        "evento": "S-2210",
        "codigo_erro": "E460",
        "titulo": "CPF do trabalhador acidentado inválido ou irregular na CAT S-2210",
        "descricao": "S-2210 (Comunicação de Acidente de Trabalho) rejeitado com E460. O CPF do trabalhador acidentado informado no evento não está cadastrado na Receita Federal ou encontra-se em situação irregular, impedindo o registro da CAT e do acidente junto ao INSS.",
        "causa_raiz": "O eSocial valida o CPF de todo trabalhador declarado em eventos de saúde e segurança do trabalho contra a base da RFB. No contexto do S-2210, o CPF pode estar incorreto por erro de digitação no momento do acidente, o trabalhador pode ser estrangeiro sem CPF brasileiro regularizado, ou o CPF pode estar em situação 'Pendente de Regularização' na RFB. A urgência é maior pois a CAT tem prazo legal de 1 dia útil.",
        "passos_resolucao": [
            "Verificar imediatamente o CPF correto do trabalhador nos documentos de admissão (CTPS, contrato, ficha de registro)",
            "Consultar a situação do CPF na RFB: https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp",
            "Comparar o CPF do S-2210 com o CPF registrado no S-2200 (admissão) do trabalhador na plataforma eSocial",
            "Se houver erro de digitação: corrigir o cpfTrab no S-2210 e retransmitir",
            "Se CPF irregular: iniciar processo emergencial de regularização junto à RFB e documentar o ocorrido para fins de prazo legal",
            "Retransmitir o S-2210 assim que o CPF estiver regular e correto"
        ],
        "validacao": "Confirmar CPF com situação 'Regular' na RFB e idêntico ao do S-2200. S-2210 aceito com cdResposta=201 e CAT registrada.",
        "tempo_estimado": "1-3h (urgente — prazo legal de 1 dia útil para CAT)",
        "impacto": "crítico",
        "tags": ["S-2210", "E460", "CAT", "CPF", "RFB", "acidente trabalho", "cpfTrab", "INSS", "prazo legal"]
    },
    {
        "id": "KB059",
        "evento": "S-1200",
        "codigo_erro": "E430",
        "titulo": "S-1200 duplicado para a competência — reenvio indevido após timeout",
        "descricao": "S-1200 (Remuneração do Trabalhador) rejeitado com E430. Já existe um S-1200 processado com sucesso para o mesmo trabalhador (mesmo CPF) e a mesma competência (perApur) no eSocial, caracterizando duplicidade. Ocorre tipicamente quando o sistema de folha reenvia automaticamente após um timeout sem verificar se o envio anterior já foi aceito.",
        "causa_raiz": "O E430 no S-1200 indica que o eSocial já possui um evento de remuneração aceito (cdResposta=201) para o par CPF/perApur. As causas mais comuns são: sistema de retry enviou o S-1200 múltiplas vezes após timeout do webservice sem checar o retorno anterior; operador retransmitiu manualmente sem consultar a plataforma; ou o sistema de integração não persistiu o nrRec do aceite anterior e gerou novo envio na próxima janela. Este erro é distinto do E428 (que trata de retificação incorreta).",
        "passos_resolucao": [
            "Consultar o S-1200 já aceito na plataforma eSocial para o trabalhador e a competência: verificar o nrRec do evento processado",
            "Confirmar que o S-1200 original está com cdResposta=201 e os valores de remuneração corretos",
            "Se os valores do S-1200 original estiverem corretos: nenhuma ação adicional é necessária — descartar o reenvio",
            "Se os valores precisarem de correção: usar o S-1200 com indRetif=2 e nrRecEvt com o nrRec do evento aceito (retificação), não reenviar como original",
            "Revisar o sistema de transmissão para implementar verificação de status antes de reenviar (consultar nrRec antes de retransmitir)",
            "Implementar persistência do nrRec de aceite para evitar reenvios após timeout"
        ],
        "validacao": "Confirmar na plataforma que o S-1200 original está processado com os valores corretos. Para correções de valor, confirmar aceite do S-1200 retificado (indRetif=2) com cdResposta=201.",
        "tempo_estimado": "1-2h",
        "impacto": "médio",
        "tags": ["S-1200", "E430", "duplicata", "remuneração", "perApur", "timeout", "retry", "nrRec", "reenvio"]
    },
    {
        "id": "KB060",
        "evento": "S-2299",
        "codigo_erro": "E529",
        "titulo": "Motivo de desligamento incompatível com a categoria do trabalhador",
        "descricao": "S-2299 (Desligamento) rejeitado com E529. O código do motivo de desligamento (mtvDeslig) informado é incompatível com a categoria do trabalhador (codCateg), o tipo de regime de trabalho (tpRegTrab), ou outros atributos do vínculo declarados no S-2200 correspondente.",
        "causa_raiz": "O eSocial define regras de compatibilidade entre motivos de desligamento e categorias de trabalhadores. Exemplos frequentes: motivo '01' (rescisão sem justa causa) não é válido para estagiários (categoria 901) que devem usar motivo '12' (término de contrato de estágio); trabalhadores domésticos têm motivos específicos distintos dos CLT; servidores públicos (regime estatutário) não podem usar motivos de rescisão da CLT; motivo de aposentadoria exige confirmação de benefício INSS ativo. A incompatibilidade entre mtvDeslig e codCateg é a principal causa de E529 no S-2299.",
        "passos_resolucao": [
            "Consultar a tabela de motivos de desligamento (Tabela 19) na documentação técnica do eSocial e verificar os motivos válidos para a categoria do trabalhador",
            "Identificar a categoria (codCateg) registrada no S-2200 do trabalhador",
            "Verificar qual código mtvDeslig é compatível com a categoria: ex. categoria 901 (estagiário) → motivo 12; categoria 10x (doméstico) → motivos específicos de doméstico",
            "Corrigir o campo mtvDeslig no XML do S-2299 com o código compatível com a categoria",
            "Para desligamentos por aposentadoria: confirmar se há benefício INSS ativo e usar o motivo correto conforme o tipo de aposentadoria",
            "Retransmitir o S-2299 com o motivo de desligamento correto"
        ],
        "validacao": "Confirmar que o mtvDeslig é compatível com a codCateg do S-2200 correspondente. S-2299 aceito com cdResposta=201 e vínculo encerrado na plataforma.",
        "tempo_estimado": "2h",
        "impacto": "alto",
        "tags": ["S-2299", "E529", "desligamento", "mtvDeslig", "categoria", "codCateg", "estagiário", "CLT", "tpRegTrab"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE ALTERAÇÃO CONTRATUAL / TABELAS
    # ──────────────────────────────────────────────────────
    {
        "id": "KB061",
        "evento": "S-2206",
        "codigo_erro": "E529",
        "titulo": "Tipo de salário ou jornada incompatível com a categoria na alteração contratual S-2206",
        "descricao": "S-2206 (Alteração de Contrato de Trabalho) rejeitado com E529. Os campos de remuneração (tpSalFx, vrSalFx) ou jornada (qtdHrsSem, tpJornada) informados na alteração contratual são incompatíveis com a categoria do trabalhador (codCateg) registrada no S-2200 original ou com o tipo de regime de trabalho declarado.",
        "causa_raiz": "O eSocial aplica regras de compatibilidade entre tipo de salário/jornada e categoria do trabalhador no evento S-2206. Exemplos frequentes: tentar aplicar salário por hora (tpSalFx=2) a um trabalhador mensalista sem alterar corretamente o tpRegJor; informar qtdHrsSem acima de 44h para categorias com regime especial de jornada; usar tpJornada incompatível com codCateg (ex: jornada de tempo parcial para categoria que exige tempo integral); ou alterar tpSalFx para valor que contradiz a categoria do vínculo estabelecida no S-2200. A tabela de compatibilidades está definida nos leiautes do eSocial e é validada no momento do processamento.",
        "passos_resolucao": [
            "Identificar os campos rejeitados consultando a mensagem de erro E529 no retorno do eSocial (campo localizacaoErro)",
            "Consultar a Tabela de Categorias do eSocial e verificar as restrições de tpSalFx e tpJornada para a codCateg do trabalhador",
            "Verificar o S-2200 original do trabalhador para confirmar a categoria e o regime de trabalho registrados",
            "Corrigir os campos incompatíveis no S-2206: alinhar tpSalFx, vrSalFx, qtdHrsSem e tpJornada com as regras da categoria",
            "Se a categoria precisar ser alterada: verificar se o eSocial permite a mudança de categoria via S-2206 ou se é necessário desligamento e nova admissão",
            "Retransmitir o S-2206 com os dados corrigidos e compatíveis com a categoria do trabalhador"
        ],
        "validacao": "Confirmar S-2206 aceito com cdResposta=201. Verificar na plataforma eSocial que os dados contratuais alterados estão refletidos corretamente no histórico do vínculo.",
        "tempo_estimado": "2-3h",
        "impacto": "médio",
        "tags": ["S-2206", "E529", "alteração contratual", "tpSalFx", "jornada", "qtdHrsSem", "categoria", "codCateg", "tpJornada"]
    },
    {
        "id": "KB062",
        "evento": "S-2206",
        "codigo_erro": "E601",
        "titulo": "Data de alteração contratual S-2206 fora da janela de transmissão permitida",
        "descricao": "S-2206 (Alteração de Contrato de Trabalho) rejeitado com E601. A data de alteração contratual informada no campo dtAlt está fora da janela de transmissão aceita pelo eSocial, seja por ser anterior ao prazo mínimo retroativo permitido ou por ser futura em relação à data de transmissão.",
        "causa_raiz": "O eSocial impõe janelas de transmissão para eventos não periódicos como o S-2206. O E601 ocorre quando: a data da alteração contratual (dtAlt) é anterior ao limite retroativo definido pelo eSocial para o grupo de empregadores (geralmente vinculado ao início da obrigatoriedade); a data é futura por erro de digitação no campo (ex: ano 2026 em vez de 2025); ou a alteração refere-se a um período cuja folha já foi fechada via S-1299 sem que a mudança contratual tenha sido registrada antes do fechamento. A janela de retroatividade varia por grupo de empregadores conforme o cronograma do eSocial.",
        "passos_resolucao": [
            "Verificar a data correta da alteração contratual nos documentos internos (aditivo contratual, acordo coletivo, decisão judicial)",
            "Confirmar a data de transmissão atual e verificar se a dtAlt não está no futuro por erro de digitação",
            "Consultar o calendário de obrigatoriedades do eSocial para o grupo do empregador e verificar a data de início que limita a retroatividade",
            "Se a data for retroativa além do limite: contatar o e-CAC da RFB para orientação sobre envio extemporâneo",
            "Se a data for futura por erro de digitação: corrigir o campo dtAlt no XML com a data real da alteração",
            "Retransmitir o S-2206 com a dtAlt correta e dentro da janela de transmissão"
        ],
        "validacao": "Confirmar S-2206 aceito com cdResposta=201 e data de alteração registrada corretamente no histórico do vínculo na plataforma eSocial.",
        "tempo_estimado": "1-2h (variável se exigir contato com RFB para retroativo)",
        "impacto": "médio",
        "tags": ["S-2206", "E601", "alteração contratual", "dtAlt", "janela transmissão", "retroativo", "prazo", "data futura"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE PAGAMENTO / BENEFÍCIO
    # ──────────────────────────────────────────────────────
    {
        "id": "KB063",
        "evento": "S-4000",
        "codigo_erro": "E312",
        "titulo": "S-4000 rejeitado — pagamento a beneficiário sem evento de remuneração correspondente",
        "descricao": "S-4000 (Informações de Pagamentos a Beneficiários) rejeitado com E312. O eSocial não localiza um evento de remuneração previamente aceito (S-1200, S-1202 ou verbas rescisórias do S-2299) que fundamente o pagamento declarado no S-4000 para o CPF do beneficiário e a competência informados.",
        "causa_raiz": "O S-4000 é um evento de pagamento que deve obrigatoriamente corresponder a eventos de remuneração já aceitos na plataforma eSocial. O E312 ocorre quando: o S-1200 ou S-1202 correspondente ao pagamento não foi transmitido ou está com erro; a competência (perApur) do S-4000 diverge da competência do evento de remuneração; o CPF do beneficiário no S-4000 não coincide com o CPF do evento de remuneração processado; ou o empregador tenta declarar pagamentos por serviços autônomos sem o correspondente S-2300 ativo e S-1202 aceito. O eSocial exige rastreabilidade entre pagamento e remuneração declarada.",
        "passos_resolucao": [
            "Consultar na plataforma eSocial os eventos de remuneração (S-1200, S-1202) aceitos para o CPF do beneficiário e a competência informada no S-4000",
            "Verificar se o S-1200 ou S-1202 correspondente está processado com cdResposta=201",
            "Se o evento de remuneração não existir: enviar o S-1200 (empregado CLT) ou S-1202 (TSVE/autônomo) antes de retransmitir o S-4000",
            "Confirmar que o CPF do beneficiário e a competência no S-4000 são idênticos aos do evento de remuneração correspondente",
            "Para pagamentos de trabalhadores autônomos: verificar se o S-2300 está ativo e se o S-1202 foi enviado para a competência",
            "Retransmitir o S-4000 somente após confirmação do evento de remuneração correspondente aceito"
        ],
        "validacao": "Verificar que existe S-1200 ou S-1202 aceito (cdResposta=201) para o mesmo CPF e competência antes de reenviar. S-4000 aceito com cdResposta=201 e retenção de IR/INSS calculada.",
        "tempo_estimado": "3-4h",
        "impacto": "alto",
        "tags": ["S-4000", "E312", "pagamento", "S-1200", "S-1202", "remuneração", "beneficiário", "competência", "autônomo"]
    },
    {
        "id": "KB064",
        "evento": "S-2400",
        "codigo_erro": "E350",
        "titulo": "Data de início do benefício INSS anterior ao afastamento registrado no S-2230",
        "descricao": "S-2400 (Cadastro de Beneficiário — Início do Benefício) rejeitado com E350. A data de início do benefício previdenciário (dtIniBenef) informada é anterior à data de início do afastamento (dtIniAfast) registrado no S-2230 para o mesmo trabalhador, criando inconsistência temporal no histórico do vínculo.",
        "causa_raiz": "O eSocial valida a consistência temporal entre eventos relacionados ao mesmo trabalhador. Para benefícios previdenciários por incapacidade (auxílio-doença, aposentadoria por invalidez), a lógica exige que o afastamento declarado no S-2230 seja anterior ou contemporâneo ao início do benefício no S-2400. O E350 ocorre quando: a data do afastamento no S-2230 foi lançada incorretamente como posterior ao início do benefício; o S-2230 foi enviado com data errada; o benefício foi concedido retroativamente pelo INSS a uma data anterior ao afastamento declarado; ou o S-2400 está sendo enviado sem que o S-2230 correspondente tenha sido previamente transmitido e aceito.",
        "passos_resolucao": [
            "Consultar o S-2230 ativo do trabalhador na plataforma eSocial e verificar a dtIniAfast registrada",
            "Verificar a Carta de Concessão do benefício pelo INSS para confirmar a data real de início (dtIniBenef)",
            "Se o S-2230 tiver data incorreta: retificar o S-2230 com a dtIniAfast correta antes de retransmitir o S-2400",
            "Se não houver S-2230: enviar o S-2230 com a data de início do afastamento antes de transmitir o S-2400",
            "Garantir que a dtIniAfast do S-2230 seja igual ou anterior à dtIniBenef do S-2400",
            "Retransmitir o S-2400 após confirmação do S-2230 com datas consistentes e aceito (cdResposta=201)"
        ],
        "validacao": "Verificar que S-2230 está aceito com dtIniAfast ≤ dtIniBenef do S-2400. S-2400 aceito com cdResposta=201 e benefício registrado com a data correta na plataforma.",
        "tempo_estimado": "2-3h",
        "impacto": "alto",
        "tags": ["S-2400", "E350", "benefício INSS", "afastamento", "S-2230", "dtIniBenef", "dtIniAfast", "auxílio-doença", "aposentadoria"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE TABELAS DE EMPREGADOR
    # ──────────────────────────────────────────────────────
    {
        "id": "KB065",
        "evento": "S-1050",
        "codigo_erro": "E100",
        "titulo": "Horário de trabalho já cadastrado — duplicata na tabela S-1050",
        "descricao": "S-1050 (Tabela de Horários de Trabalho) rejeitado com E100. O código do horário de trabalho (codHorContrat) informado já existe na tabela do empregador na plataforma eSocial. O evento S-1050 está sendo enviado como novo (indRetif=1) mas o registro já foi previamente cadastrado, caracterizando duplicidade.",
        "causa_raiz": "O S-1050 mantém a tabela de horários de trabalho do empregador no eSocial. O E100 ocorre porque: o codHorContrat informado já foi cadastrado em um S-1050 anterior aceito; o sistema de integração reenviou o S-1050 original após timeout sem verificar se o aceite anterior foi processado; houve tentativa de inclusão de novo horário reutilizando um código já existente; ou o operador criou um registro sem verificar os horários já cadastrados na plataforma. Para atualizar um horário já cadastrado, deve-se usar indRetif=2 (retificação) com o nrRecEvt do S-1050 original, nunca enviar um novo evento com o mesmo codHorContrat.",
        "passos_resolucao": [
            "Consultar a tabela de horários cadastrados na plataforma eSocial para identificar o S-1050 existente com o mesmo codHorContrat",
            "Copiar o nrRec do S-1050 já aceito com o codHorContrat em questão",
            "Se o objetivo for atualizar o horário: alterar o S-1050 para indRetif=2 e preencher nrRecEvt com o nrRec do evento original",
            "Se o objetivo for criar um horário diferente: utilizar um codHorContrat ainda não cadastrado na tabela",
            "Retransmitir o S-1050 como retificação (indRetif=2) ou com novo código de horário conforme o caso",
            "Revisar o processo de geração de codHorContrat no sistema de integração para evitar duplicatas futuras"
        ],
        "validacao": "Confirmar S-1050 aceito com cdResposta=201. Verificar na tabela de horários da plataforma que o registro está atualizado ou que o novo código foi criado corretamente.",
        "tempo_estimado": "1h",
        "impacto": "baixo",
        "tags": ["S-1050", "E100", "horário trabalho", "codHorContrat", "duplicata", "tabela", "indRetif", "nrRecEvt"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE TSVE (TRABALHADOR SEM VÍNCULO DE EMPREGO)
    # ──────────────────────────────────────────────────────
    {
        "id": "KB066",
        "evento": "S-2300",
        "codigo_erro": "E312",
        "titulo": "Alteração ou encerramento de TSVE rejeitado — S-2300 não encontrado para o autônomo",
        "descricao": "Evento da família TSVE (S-2306 — Alteração dos Dados Cadastrais, ou S-2399 — Término) rejeitado com E312. O eSocial não localiza um S-2300 (TSVE — Início) ativo para o CPF do trabalhador autônomo e o empregador informados, tornando qualquer operação subsequente sobre esse trabalhador inválida.",
        "causa_raiz": "O S-2300 é o evento que abre o período de atividade do Trabalhador Sem Vínculo de Emprego (autônomo, contribuinte individual, estagiário sem CLT). Sem um S-2300 ativo e aceito, nenhum evento de alteração cadastral (S-2306) ou encerramento (S-2399) pode ser processado. O E312 nesse contexto ocorre quando: o S-2300 nunca foi transmitido para esse trabalhador; o S-2300 foi enviado com CPF diferente do informado no S-2306/S-2399; o S-2300 foi excluído indevidamente via S-3000; ou o S-2306/S-2399 foi enviado antes do aceite do S-2300. Este cenário é complementar ao KB054, que cobre exclusivamente o S-2399, pois aqui a ausência de S-2300 impede também alterações cadastrais via S-2306.",
        "passos_resolucao": [
            "Consultar o CPF do trabalhador autônomo na plataforma eSocial e verificar se existe S-2300 ativo para o empregador",
            "Se não existir S-2300 ativo: enviar o S-2300 com a data de início real da prestação de serviços do trabalhador",
            "Verificar se houve exclusão indevida via S-3000 consultando o histórico de eventos do CPF na plataforma",
            "Aguardar processamento e aceite do S-2300 (cdResposta=201) antes de tentar qualquer S-2306 ou S-2399",
            "Confirmar que o CPF no S-2306/S-2399 é idêntico ao CPF registrado no S-2300 aceito",
            "Retransmitir o S-2306 ou S-2399 somente após confirmação do S-2300 ativo na plataforma"
        ],
        "validacao": "Confirmar S-2300 aceito com cdResposta=201 e período de atividade TSVE ativo na plataforma. Reenvio do S-2306 ou S-2399 aceito com cdResposta=201.",
        "tempo_estimado": "3-4h",
        "impacto": "alto",
        "tags": ["S-2300", "E312", "TSVE", "autônomo", "contribuinte individual", "S-2306", "S-2399", "cpfTrab", "período atividade"]
    },

    # ──────────────────────────────────────────────────────
    # ERROS DE CONECTIVIDADE E CERTIFICADO
    # ──────────────────────────────────────────────────────
    {
        "id": "KB067",
        "evento": "Qualquer",
        "codigo_erro": "E002",
        "titulo": "Falha de conectividade SSL/TLS com o webservice eSocial",
        "descricao": "Erro E002 na transmissão de lotes ao webservice do eSocial. O erro indica falha de handshake SSL/TLS na camada de transporte, impedindo o estabelecimento da conexão segura entre o middleware do empregador e o endpoint do governo. Nenhum evento é transmitido — o erro ocorre antes mesmo do processamento dos XMLs pelo servidor.",
        "causa_raiz": "O E002 de conectividade SSL/TLS tem múltiplas causas na camada de rede e segurança: os certificados raiz da ICP-Brasil não estão instalados ou estão desatualizados no truststore do servidor de transmissão; a versão do protocolo TLS do middleware é incompatível com os requisitos do webservice (o governo exige TLS 1.2 ou superior, rejeitando TLS 1.0 e 1.1); o firewall corporativo bloqueia ou realiza inspeção SSL no tráfego HTTPS para os endpoints do eSocial; o proxy corporativo quebra o handshake mTLS; ou o certificado digital do empregador não está sendo apresentado corretamente na camada de transporte. Esta situação é distinta do E214 (certificado expirado) pois o E002 ocorre na camada de transporte, antes da validação do conteúdo XML.",
        "passos_resolucao": [
            "Verificar conectividade básica com o endpoint do eSocial usando curl ou ferramenta equivalente contra https://www.esocial.gov.br",
            "Verificar se os certificados raiz da ICP-Brasil estão instalados e atualizados no truststore do servidor de transmissão",
            "Confirmar que o middleware usa TLS 1.2 ou 1.3 — versões TLS 1.0 e 1.1 são rejeitadas pelo webservice do governo",
            "Verificar as regras de firewall e proxy corporativo: os endpoints *.gov.br na porta 443 devem ter passagem direta sem inspeção SSL",
            "Testar a transmissão fora da rede corporativa (ex: via hotspot 4G) para isolar se o problema é do ambiente de rede da empresa",
            "Se o problema for no proxy: configurar exceção de SSL inspection para os domínios *.esocial.gov.br",
            "Contatar o fornecedor do middleware se o problema persistir — pode exigir atualização da biblioteca SSL/TLS utilizada"
        ],
        "validacao": "Realizar transmissão de teste e confirmar conexão estabelecida sem E002. Verificar log de transmissão para confirmar handshake TLS bem-sucedido e evento aceito.",
        "tempo_estimado": "2-4h (pode envolver equipe de redes e infraestrutura)",
        "impacto": "crítico",
        "tags": ["E002", "SSL", "TLS", "conectividade", "webservice", "firewall", "proxy", "ICP-Brasil", "handshake"]
    },
    {
        "id": "KB068",
        "evento": "Qualquer",
        "codigo_erro": "E203",
        "titulo": "CNPJ do empregador suspenso ou inapto na RFB — transmissão bloqueada",
        "descricao": "Todos os eventos rejeitados com E203. O CNPJ do empregador informado no ideEmpregador está com situação cadastral irregular na Receita Federal do Brasil — suspenso, inapto, baixado ou cancelado — impedindo qualquer transmissão de eventos ao eSocial enquanto a irregularidade não for sanada junto à RFB.",
        "causa_raiz": "O eSocial valida a situação cadastral do CNPJ do empregador antes de processar qualquer evento. O status 'suspenso' ocorre tipicamente por falta de entrega de declarações obrigatórias (DCTF, ECF, DEFIS, DASN); 'inapto' indica que o CNPJ não entregou obrigações acessórias por dois ou mais exercícios consecutivos; 'baixado' significa que o CNPJ foi encerrado formalmente. Em todos os casos, o eSocial bloqueia totalmente a transmissão até a regularização. Esta situação é diferente do E469 (CNPJ do estabelecimento inativo em vínculo específico) pois o E203 bloqueia o empregador principal e afeta todos os eventos sem distinção.",
        "passos_resolucao": [
            "Consultar a situação cadastral do CNPJ na RFB: https://servicos.receita.fazenda.gov.br/servicos/cnpjreva/Cnpjreva_Solicitacao.asp",
            "Identificar o motivo da irregularidade: verificar obrigações acessórias pendentes no e-CAC (https://cav.receita.fazenda.gov.br)",
            "Regularizar a situação: entregar as declarações em atraso (DCTF, ECF, DEFIS) ou retificar as irregularidades apontadas pela RFB",
            "Para CNPJ 'suspenso': entregar as declarações pendentes e aguardar a atualização da situação pela RFB (pode levar 24-72h após entrega)",
            "Para CNPJ 'inapto': além das declarações, pode ser necessário protocolo formal de reativação junto à RFB com acompanhamento de contabilista",
            "Após regularização, confirmar nova situação como 'Ativa' na RFB antes de retransmitir os eventos pendentes"
        ],
        "validacao": "Confirmar CNPJ com situação 'Ativa' na consulta da RFB antes de retransmitir. Reenvio dos eventos aceito sem E203 após regularização.",
        "tempo_estimado": "Variável — regularização da RFB pode levar de horas a dias",
        "impacto": "crítico",
        "tags": ["E203", "CNPJ", "RFB", "suspenso", "inapto", "situação cadastral", "empregador", "bloqueio transmissão", "e-CAC"]
    },
    {
        "id": "KB069",
        "evento": "Qualquer",
        "codigo_erro": "E216",
        "titulo": "Certificado digital A3 revogado pela AC — diferente de certificado expirado",
        "descricao": "Eventos rejeitados com E216. O certificado digital A3 (hardware token ou smartcard) utilizado para assinar e transmitir os eventos foi revogado pela Autoridade Certificadora (AC) emissora antes do seu vencimento natural, tornando a assinatura digital inválida. Este erro é distinto do E214 (certificado expirado) pois a revogação é um ato deliberado da AC ou do titular, não decorrente do prazo de validade.",
        "causa_raiz": "A revogação do certificado A3 é verificada em tempo real pelo eSocial via Lista de Certificados Revogados (LCR/CRL) ou protocolo OCSP da ICP-Brasil em cada transmissão. As causas mais comuns de revogação são: comprometimento ou suspeita de comprometimento da chave privada do token; solicitação do titular por perda ou roubo do dispositivo smartcard/token; mudança dos dados do titular (razão social, CNPJ) que exige emissão de novo certificado; ou revogação realizada pela AC por determinação judicial ou infração às políticas da ICP-Brasil. Uma vez revogado, o certificado não pode ser reativado — é obrigatória a emissão de novo certificado junto à AC.",
        "passos_resolucao": [
            "Confirmar a revogação consultando a CRL da AC emissora ou usando verificação OCSP com o número de série do certificado",
            "Contatar a Autoridade Certificadora (ex: Serasa, Certisign, Valid, Soluti) para confirmar o motivo e a data da revogação",
            "URGENTE: Se a revogação ocorreu por comprometimento de chave, fazer levantamento de todos os eventos assinados com o certificado revogado para avaliação de validade jurídica",
            "Solicitar emissão de novo certificado A3 junto à AC — a revogação não pode ser desfeita, é necessário novo certificado",
            "Instalar o novo certificado no dispositivo token/smartcard e configurar o middleware de transmissão com o novo certificado",
            "Retransmitir os eventos pendentes com o novo certificado válido",
            "Revisar o processo de custódia do token/smartcard e implementar controles de acesso para evitar recorrência"
        ],
        "validacao": "Verificar que o novo certificado está ativo e não revogado na CRL da AC emissora. Transmissão de evento de teste aceita sem E216 com o novo certificado.",
        "tempo_estimado": "4-8h (emissão de novo certificado A3 depende do processo da AC)",
        "impacto": "crítico",
        "tags": ["E216", "certificado digital", "A3", "revogado", "CRL", "OCSP", "ICP-Brasil", "token", "smartcard"]
    },
]
