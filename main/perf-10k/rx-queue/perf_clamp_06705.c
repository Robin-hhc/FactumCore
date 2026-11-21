/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06705(unsigned int count)
{
    const unsigned int limit = 200u;
    return count > limit ? limit : count;
}
