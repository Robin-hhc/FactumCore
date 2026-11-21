/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09640(unsigned int count)
{
    const unsigned int limit = 46u;
    return count > limit ? limit : count;
}
