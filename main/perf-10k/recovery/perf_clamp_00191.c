/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00191(unsigned int count)
{
    const unsigned int limit = 18u;
    return count > limit ? limit : count;
}
