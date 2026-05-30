using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;

namespace Energy_Truth_WEB_API.Services.Customer
{
    public class CustomerService : ICustomerService
    {
        private readonly ICustomerRepository _customerRepository;

        public CustomerService(ICustomerRepository customerRepository)
        {
            _customerRepository = customerRepository;
        }

        public async Task<int> CreateCustomerAsync(CreateCustomerDTO customerDTO)
        {
            var existingCustomer = await GetCustomerByEmailAsync(customerDTO.Email);
            if (existingCustomer != 0)
            {
                throw new InvalidOperationException("Dit e-mailadres is al geregistreerd.");
            }

            var customer = await _customerRepository.CreateCustomerAsync(customerDTO);
            return customer;
        }

        public async Task<int> GetCustomerByEmailAsync(string email)
        {
            var customer = await _customerRepository.GetCustomerByEmailAsync(email);
            return customer;
        }

        public async Task<LoggedInUser> LoginCustomerAsync(LoginRequestDTO loginRequestDTO)
        {
            var customer = await _customerRepository.ValidateCredentialsAsync(loginRequestDTO);

            if (customer == null)
            {
                return null;
            }

            return customer;
        }
    }
}
