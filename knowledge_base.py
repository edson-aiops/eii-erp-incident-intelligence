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
        "tags": ["S-1200", "E320", "competência", "prazo", "perApur", "extemporâneo", "remuneração"]
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
]
