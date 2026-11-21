/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01280(unsigned int count)
{
    const unsigned int limit = 105u;
    return count > limit ? limit : count;
}
