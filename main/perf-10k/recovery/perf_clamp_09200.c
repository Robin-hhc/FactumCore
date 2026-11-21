/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09200(unsigned int count)
{
    const unsigned int limit = 36u;
    return count > limit ? limit : count;
}
