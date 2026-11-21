/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02640(unsigned int count)
{
    const unsigned int limit = 68u;
    return count > limit ? limit : count;
}
