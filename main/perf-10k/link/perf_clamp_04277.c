/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04277(unsigned int count)
{
    const unsigned int limit = 9u;
    return count > limit ? limit : count;
}
